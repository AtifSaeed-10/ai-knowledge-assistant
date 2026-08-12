"""
RAG V2 Phase 3 — FastEmbed / ONNX cross-encoder reranking.

Isolated so the model can be swapped later without touching hybrid retrieval.
Uses BAAI/bge-reranker-base by default via TextCrossEncoder.
"""

from __future__ import annotations

import math
import threading
from typing import Any

from config import (
    RERANK_MIN_SCORE,
    RERANK_TOP_K,
    RERANKER_MODEL,
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
    reranker_service: CrossEncoderReranker | None = None,
) -> list[dict[str, Any]]:
    """
    Rerank an already-fused, deduplicated candidate pool.

    Preserves dense_distance / bm25_score / rrf_score separately and adds
    reranker_score + relevance. Final order is by reranker_score descending.
    """
    limit = top_k if top_k is not None else RERANK_TOP_K
    score_floor = RERANK_MIN_SCORE if min_score is None else min_score
    service = reranker_service or reranker

    if not candidates or limit <= 0:
        return []

    # Defensive dedupe by chunk id (fusion should already have done this).
    unique: dict[str, dict[str, Any]] = {}
    for cand in candidates:
        chunk_id = cand.get("id")
        if not chunk_id:
            continue
        if chunk_id not in unique:
            unique[chunk_id] = cand
    pool = list(unique.values())
    if not pool:
        return []

    documents = [c.get("text") or "" for c in pool]
    scores = service.score(query, documents)

    scored: list[dict[str, Any]] = []
    for cand, raw_score in zip(pool, scores):
        item = {
            "id": cand["id"],
            "text": cand.get("text") or "",
            "metadata": cand.get("metadata") or {},
            "dense_distance": cand.get("dense_distance"),
            "bm25_score": cand.get("bm25_score"),
            "rrf_score": float(cand.get("rrf_score") or 0.0),
            "sources": list(cand.get("sources") or []),
            "reranker_score": float(raw_score),
            "relevance": sigmoid_relevance(float(raw_score)),
        }
        if score_floor is not None and item["reranker_score"] < score_floor:
            continue
        scored.append(item)

    scored.sort(
        key=lambda item: (-item["reranker_score"], item["id"])
    )
    return scored[:limit]


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
    limit = top_k if top_k is not None else RERANK_TOP_K
    if reason:
        print(f"WARNING: RERANKER FALLBACK: {reason}")

    unique: dict[str, dict[str, Any]] = {}
    for cand in candidates:
        chunk_id = cand.get("id")
        if chunk_id and chunk_id not in unique:
            unique[chunk_id] = cand

    ranked = sorted(
        unique.values(),
        key=lambda item: (-float(item.get("rrf_score") or 0.0), item["id"]),
    )

    max_rrf = float(ranked[0].get("rrf_score") or 0.0) if ranked else 0.0
    results: list[dict[str, Any]] = []
    for cand in ranked[:limit]:
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
    return results
