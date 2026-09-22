"""
RAG V2 Phase 3 — FastEmbed / ONNX cross-encoder reranking.

Isolated so the model can be swapped later without touching hybrid retrieval.
Default: BAAI/bge-reranker-base. A/B alternative: Xenova/ms-marco-MiniLM-L-6-v2
(config.RERANKER_MODEL_MINILM).
"""

from __future__ import annotations

import math
import re
import threading
from difflib import SequenceMatcher
from typing import Any

from config import (
    CITATION_MIN_RELEVANCE,
    EVIDENCE_FALLBACK_MIN_RERANK,
    EVIDENCE_NEAR_DUP_RATIO,
    RECALL_TOP_K,
    RERANK_MAX_CHARS,
    RERANK_MIN_SCORE,
    RERANKER_MODEL,
)
from rerank_calibration import (
    adaptive_keep_candidates,
    calibrated_relevance,
    resolve_rerank_model_name,
)


class RerankerUnavailableError(RuntimeError):
    """Raised when the cross-encoder cannot be loaded or used."""


def sigmoid_relevance(score: float) -> int:
    """Map raw reranker logit → citation relevance percent [0, 100]."""
    # Numerically stable sigmoid
    if score >= 0:
        z = math.exp(-score)
        prob = 1.0 / (1.0 + z)
    else:
        z = math.exp(score)
        prob = z / (1.0 + z)
    return int(max(0, min(100, round(prob * 100))))


def truncate_for_rerank(
    text: str,
    max_chars: int | None = None,
) -> str:
    """
    Deterministic head+tail truncation for BGE scoring only.

    Full chunk text is preserved for LLM context / citations elsewhere.
    """
    limit = RERANK_MAX_CHARS if max_chars is None else max_chars
    if limit <= 0 or len(text) <= limit:
        return text

    marker = " ... "
    # Prefer keeping more of the beginning (definitions/headings often lead).
    head = max(1, int(limit * 0.75))
    tail = limit - head - len(marker)
    if tail < 1:
        return text[:limit]
    return text[:head] + marker + text[-tail:]


def dedupe_by_chunk_id(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []
    for cand in candidates:
        chunk_id = cand.get("id")
        if not chunk_id or chunk_id in unique:
            continue
        unique[chunk_id] = cand
        ordered.append(cand)
    return ordered


def page_slot_key(metadata: dict[str, Any]) -> tuple[str, int]:
    """Stable (document, page) key for evidence-slot diversification."""
    doc_id = str(metadata.get("document_id") or "")
    page = metadata.get("page_number")
    if page is None:
        page = metadata.get("page_start")
    try:
        page_num = int(page)
    except (TypeError, ValueError):
        page_num = -1
    return (doc_id, page_num)


def normalize_evidence_text(text: str) -> str:
    """Lowercase + collapse whitespace for overlap comparisons."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def text_overlap_ratio(text_a: str, text_b: str) -> float:
    """
    Estimate how much two chunk texts substantially overlap [0.0, 1.0].

    Uses substring containment (common with chunk overlap) and SequenceMatcher
    for partial overlap. Full text is compared; rerank truncation is separate.
    """
    a = normalize_evidence_text(text_a)
    b = normalize_evidence_text(text_b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if shorter in longer:
        return len(shorter) / len(longer)

    return SequenceMatcher(None, a, b).ratio()


def suppress_near_duplicates(
    candidates: list[dict[str, Any]],
    overlap_threshold: float | None = None,
) -> list[dict[str, Any]]:
    """
    Drop lower-scored chunks that substantially overlap a kept chunk.

    Candidates are processed in reranker-score order so the stronger hit wins.
    """
    threshold = (
        overlap_threshold
        if overlap_threshold is not None
        else EVIDENCE_NEAR_DUP_RATIO
    )
    if not candidates:
        return []

    def _sort_key(item: dict[str, Any]) -> tuple:
        rerank = item.get("reranker_score")
        rerank_sort = float(rerank) if rerank is not None else -1e9
        return (
            -rerank_sort,
            -float(item.get("rrf_score") or 0.0),
            str(item.get("id") or ""),
        )

    ranked = sorted(candidates, key=_sort_key)
    kept: list[dict[str, Any]] = []

    for cand in ranked:
        text = cand.get("text") or ""
        is_near_dup = False
        for existing in kept:
            overlap = text_overlap_ratio(text, existing.get("text") or "")
            if overlap >= threshold:
                is_near_dup = True
                break
        if not is_near_dup:
            kept.append(cand)

    return kept


def filter_min_relevance(
    candidates: list[dict[str, Any]],
    min_relevance: int | None,
) -> list[dict[str, Any]]:
    if min_relevance is None:
        return list(candidates)
    floor = int(min_relevance)
    return [
        cand
        for cand in candidates
        if int(cand.get("relevance") or 0) >= floor
    ]


def diversify_by_page(
    candidates: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """
    Pick up to top_k chunks with at most one slot per document page.

    Keeps the highest-scoring chunk per page; does not fill spare slots
    with additional chunks from the same page.
    """
    if top_k <= 0 or not candidates:
        return []

    def _sort_key(item: dict[str, Any]) -> tuple:
        rerank = item.get("reranker_score")
        rerank_sort = float(rerank) if rerank is not None else -1e9
        return (
            -rerank_sort,
            -float(item.get("rrf_score") or 0.0),
            str(item.get("id") or ""),
        )

    ranked = sorted(candidates, key=_sort_key)
    selected: list[dict[str, Any]] = []
    seen_pages: set[tuple[str, int]] = set()

    for cand in ranked:
        meta = cand.get("metadata") or {}
        slot = page_slot_key(meta)
        if slot in seen_pages:
            continue
        seen_pages.add(slot)
        selected.append(cand)
        if len(selected) >= top_k:
            break

    return selected


def _evidence_sort_key(item: dict[str, Any]) -> tuple:
    rerank = item.get("reranker_score")
    rerank_sort = float(rerank) if rerank is not None else -1e9
    return (
        -rerank_sort,
        -float(item.get("rrf_score") or 0.0),
        str(item.get("id") or ""),
    )


def has_dual_retrieval_support(candidate: dict[str, Any]) -> bool:
    """True when fused metadata shows both dense and BM25 retrieval paths."""
    sources = candidate.get("sources") or []
    source_set = {str(source).lower() for source in sources}
    return "dense" in source_set and "bm25" in source_set


def is_citation_eligible(
    candidate: dict[str, Any],
    min_relevance: int | None = None,
) -> bool:
    """True when a recall-pool chunk may receive an E# (citation pool)."""
    floor = (
        CITATION_MIN_RELEVANCE if min_relevance is None else int(min_relevance)
    )
    return int(candidate.get("relevance") or 0) >= floor


def _annotate_pools(
    items: list[dict[str, Any]],
    *,
    recall_fallback: bool,
    gating_path: str | None = None,
) -> list[dict[str, Any]]:
    for item in items:
        item["recall_fallback"] = bool(recall_fallback)
        item["citation_eligible"] = is_citation_eligible(item)
        if gating_path is not None:
            item["gating_path"] = gating_path
    return items


def dual_source_fallback_candidates(
    candidates: list[dict[str, Any]],
    min_rerank_score: float | None = None,
) -> list[dict[str, Any]]:
    """
    Admit a single top reranked chunk when relevance filtering emptied the pool.

    Only used for MiniLM false negatives: dual hybrid support + weakly negative
    but not deeply irrelevant raw reranker score.
    """
    if not candidates:
        return []

    floor = (
        min_rerank_score
        if min_rerank_score is not None
        else EVIDENCE_FALLBACK_MIN_RERANK
    )
    top = sorted(candidates, key=_evidence_sort_key)[0]
    rerank = top.get("reranker_score")
    if rerank is None:
        return []
    if float(rerank) <= floor:
        return []
    if not has_dual_retrieval_support(top):
        return []
    return [top]


def select_evidence(
    candidates: list[dict[str, Any]],
    top_k: int,
    min_relevance: int | None = None,
) -> list[dict[str, Any]]:
    """
    Build the LLM recall pool from a scored candidate list.

    Prefer chunks at/above the (calibrated) evidence floor, plus near-tied
    neighbors. Dual-source MiniLM rescue and recall-first fallback still
    apply when the floor would empty a nonempty pool. Citation eligibility
    is annotated separately.
    """
    kept, gating_path = adaptive_keep_candidates(
        candidates,
        min_relevance=min_relevance,
    )
    used_recall_fallback = gating_path == "recall_fallback"
    deduped = suppress_near_duplicates(kept)
    selected = diversify_by_page(deduped, top_k)
    return _annotate_pools(
        selected,
        recall_fallback=used_recall_fallback,
        gating_path=gating_path,
    )


def dedupe_exact_text(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """
    Keep one representative per exact chunk text.

    Prefers higher rrf_score, then lexicographically smaller id.
    Returns (unique_candidates, number_removed).
    """
    best_by_text: dict[str, dict[str, Any]] = {}
    text_order: list[str] = []

    for cand in candidates:
        text = cand.get("text") or ""
        prev = best_by_text.get(text)
        if prev is None:
            best_by_text[text] = cand
            text_order.append(text)
            continue

        prev_rrf = float(prev.get("rrf_score") or 0.0)
        cur_rrf = float(cand.get("rrf_score") or 0.0)
        if cur_rrf > prev_rrf or (
            cur_rrf == prev_rrf and str(cand.get("id")) < str(prev.get("id"))
        ):
            best_by_text[text] = cand

    unique = [best_by_text[t] for t in text_order]
    removed = len(candidates) - len(unique)
    return unique, removed


class CrossEncoderReranker:
    """
    Process-wide lazy singleton around FastEmbed TextCrossEncoder.

    Load once; reuse for every query. Failed loads are remembered so we do
    not hammer downloads — callers use explicit fallback instead.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or RERANKER_MODEL
        self._lock = threading.RLock()
        self._model = None
        self._load_error: str | None = None
        self._load_attempted = False

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def ensure_loaded(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            if self._load_attempted and self._load_error:
                raise RerankerUnavailableError(self._load_error)

            self._load_attempted = True
            try:
                from fastembed.rerank.cross_encoder import TextCrossEncoder

                print(f"Loading reranker once: {self.model_name}")
                self._model = TextCrossEncoder(model_name=self.model_name)
                # Touch the model so first-query download/init happens here.
                list(self._model.rerank("ping", ["pong"]))
                self._load_error = None
                print(f"Reranker ready: {self.model_name}")
            except Exception as exc:  # noqa: BLE001 — surface any load failure
                self._model = None
                self._load_error = (
                    f"Failed to load reranker '{self.model_name}': {exc}"
                )
                print(f"WARNING: {self._load_error}")
                raise RerankerUnavailableError(self._load_error) from exc

    def score(self, query: str, documents: list[str]) -> list[float]:
        self.ensure_loaded()
        assert self._model is not None
        if not documents:
            return []
        return [float(s) for s in self._model.rerank(query, documents)]

    def reset_for_tests(self) -> None:
        """Test helper: clear loaded state."""
        with self._lock:
            self._model = None
            self._load_error = None
            self._load_attempted = False


# Shared singleton used by the retrieval pipeline.
reranker = CrossEncoderReranker()


def rerank_candidates(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    top_k: int | None = None,
    min_score: float | None = None,
    max_chars: int | None = None,
    reranker_service: CrossEncoderReranker | None = None,
    stats_out: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Rerank an already-fused candidate pool.

    Steps:
      1) dedupe by chunk id
      2) dedupe by exact text (score one copy)
      3) score truncated text with the configured cross-encoder
      4) return the recall pool (top_k, full original text)
    """
    limit = top_k if top_k is not None else RECALL_TOP_K
    score_floor = RERANK_MIN_SCORE if min_score is None else min_score
    char_limit = RERANK_MAX_CHARS if max_chars is None else max_chars
    service = reranker_service or reranker

    if not candidates or limit <= 0:
        if stats_out is not None:
            stats_out.update(
                {
                    "input_count": 0,
                    "unique_count": 0,
                    "deduped_count": 0,
                    "recall_fallback": False,
                    "selected_count": 0,
                }
            )
        return []

    id_deduped = dedupe_by_chunk_id(candidates)
    pool, text_removed = dedupe_exact_text(id_deduped)
    if stats_out is not None:
        stats_out.update(
            {
                "input_count": len(id_deduped),
                "unique_count": len(pool),
                "deduped_count": text_removed,
            }
        )

    if not pool:
        return []

    # Truncate only the representation sent to the reranker; keep full text on candidates.
    scored_docs = [
        truncate_for_rerank(c.get("text") or "", char_limit) for c in pool
    ]
    scores = service.score(query, scored_docs)
    model_name = resolve_rerank_model_name(getattr(service, "model_name", None))

    scored: list[dict[str, Any]] = []
    for cand, raw_score in zip(pool, scores):
        logit = float(raw_score)
        scored.append(
            {
                "id": cand["id"],
                "text": cand.get("text") or "",
                "metadata": cand.get("metadata") or {},
                "dense_distance": cand.get("dense_distance"),
                "bm25_score": cand.get("bm25_score"),
                "rrf_score": float(cand.get("rrf_score") or 0.0),
                "sources": list(cand.get("sources") or []),
                "reranker_score": logit,
                "relevance": calibrated_relevance(logit, model_name),
            }
        )

    scored.sort(
        key=lambda item: (-item["reranker_score"], item["id"])
    )
    if score_floor is not None:
        above_floor = [
            item
            for item in scored
            if item["reranker_score"] >= score_floor
        ]
        if above_floor:
            scored = above_floor

    selected = select_evidence(scored, limit)
    if stats_out is not None:
        stats_out["recall_fallback"] = any(
            bool(item.get("recall_fallback")) for item in selected
        )
        stats_out["selected_count"] = len(selected)
        stats_out["gating_path"] = (
            selected[0].get("gating_path") if selected else None
        )
        stats_out["model_name"] = model_name
    return selected


def rrf_fallback_candidates(
    candidates: list[dict[str, Any]],
    *,
    top_k: int | None = None,
    reason: str = "",
) -> list[dict[str, Any]]:
    """
    Explicit fallback when the reranker is unavailable: keep RRF order,
    leave reranker_score as None, and mark relevance from RRF only.
    """
    limit = top_k if top_k is not None else RECALL_TOP_K
    if reason:
        print(f"WARNING: RERANKER FALLBACK: {reason}")

    unique = dedupe_by_chunk_id(candidates)
    # Exact-text dedupe for fallback too so TOP_K is not wasted on clones.
    unique, _ = dedupe_exact_text(unique)

    ranked = sorted(
        unique,
        key=lambda item: (-float(item.get("rrf_score") or 0.0), item["id"]),
    )

    max_rrf = float(ranked[0].get("rrf_score") or 0.0) if ranked else 0.0
    results: list[dict[str, Any]] = []
    for cand in ranked:
        rrf = float(cand.get("rrf_score") or 0.0)
        if max_rrf > 0:
            relevance = int(max(0, min(100, round((rrf / max_rrf) * 100))))
        else:
            relevance = 0
        results.append(
            {
                "id": cand["id"],
                "text": cand.get("text") or "",
                "metadata": cand.get("metadata") or {},
                "dense_distance": cand.get("dense_distance"),
                "bm25_score": cand.get("bm25_score"),
                "rrf_score": rrf,
                "sources": list(cand.get("sources") or []),
                "reranker_score": None,
                "relevance": relevance,
                "rerank_fallback": True,
            }
        )
    return select_evidence(results, limit)
