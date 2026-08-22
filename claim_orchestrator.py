"""
Claim-centric evidence orchestrator.

For each cited claim, search the full recall pool (not only citeable E# slots),
score candidates against the claim with document-agnostic lexical support, and
rebind chunk/page when a better supporting passage wins by a clear margin.

E-ID assignment stays with retrieval. This layer only rebinds the evidence
anchor behind an existing E#. PDF region mapping runs on the winner only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from citation_resolver import _normalize_token, sanitize_quote
from claim_localizer import (
    MIN_CONFIDENCE_SENTENCE,
    STATUS_EXACT,
    STATUS_SEMANTIC_SPAN,
    STATUS_SENTENCE,
    STATUS_UNSUPPORTED,
    STATUS_WEAK,
    TextSupport,
    build_token_df,
    claim_token_coverage,
    is_informative_claim,
    score_text_support,
)
from config import CLAIM_REBIND_MARGIN, CLAIM_SUPPORT_MIN
from evidence_mapping import compact_contains, infer_content_type, make_snippet, SOURCE_NONE
from document_paths import document_pdf_path
from quote_evidence import resolve_claim_evidence

# Combined ranking: distinctive claim coverage outweighs retrieval rank so a
# related-but-wrong rank-1 chunk cannot lock the citation.
_SPAN_WEIGHT = 0.40
_COVERAGE_WEIGHT = 0.45
_RELEVANCE_WEIGHT = 0.15
_STRONG_REBIND_CONFIDENCE = 0.75


@dataclass
class OrchestrationResult:
    source: dict[str, Any]
    claim_text: str
    candidates_searched: list[dict[str, Any]] = field(default_factory=list)
    rebinding_applied: bool = False
    retrieval_chunk_id: str = ""
    selected_chunk_id: str = ""
    support_status: str = STATUS_UNSUPPORTED
    support_confidence: float = 0.0


def _validate_quote_against_chunk(quote: str, chunk_text: str) -> bool:
    cleaned = sanitize_quote(quote)
    if not cleaned:
        return False
    return compact_contains(chunk_text or "", cleaned)


def _chunk_text_from_index(chunk_id: str) -> str:
    if not chunk_id:
        return ""
    from rag import get_collection

    payload = get_collection().get(ids=[str(chunk_id)], include=["documents"])
    documents = payload.get("documents") or []
    if not documents:
        return ""
    text = documents[0]
    return text if isinstance(text, str) else ""


def _candidate_text(candidate: dict[str, Any]) -> str:
    for key in ("text", "chunk_text"):
        value = candidate.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return _chunk_text_from_index(str(candidate.get("chunk_id") or ""))


def _span_component(support: TextSupport) -> float:
    if support.status == STATUS_EXACT:
        return 1.0
    if support.status in {STATUS_SENTENCE, STATUS_SEMANTIC_SPAN}:
        return float(support.confidence or 0.0)
    if support.status == STATUS_WEAK:
        return min(float(support.confidence or 0.0), 0.35)
    return 0.0


def _combined_score(span_score: float, coverage: float, relevance: int | None) -> float:
    rel = max(0, min(100, int(relevance or 0))) / 100.0
    return (
        _SPAN_WEIGHT * max(0.0, min(1.0, span_score))
        + _COVERAGE_WEIGHT * max(0.0, min(1.0, coverage))
        + _RELEVANCE_WEIGHT * rel
    )


def _public_support_status(support: TextSupport, coverage: float) -> str:
    if support.status == STATUS_EXACT:
        return "supported"
    if (
        support.status in {STATUS_SENTENCE, STATUS_SEMANTIC_SPAN}
        and float(support.confidence or 0.0) >= MIN_CONFIDENCE_SENTENCE
    ):
        return "supported"
    if coverage >= 0.55:
        return "supported"
    if support.status == STATUS_WEAK or coverage >= 0.30:
        return "weakly_supported"
    return "unsupported"


def _merge_candidate_pool(
    bound_source: dict[str, Any],
    recall_candidates: list[dict[str, Any]] | None,
    sources: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Deduped pool: recall rows (full text) plus citeable sources plus bound slot."""
    merged: dict[str, dict[str, Any]] = {}
    for row in list(recall_candidates or []) + list(sources or []) + [bound_source]:
        if not isinstance(row, dict):
            continue
        chunk_id = str(row.get("chunk_id") or "")
        if not chunk_id:
            continue
        if chunk_id not in merged:
            merged[chunk_id] = dict(row)
            continue
        current = merged[chunk_id]
        old_text = current.get("text") or current.get("chunk_text") or ""
        new_text = row.get("text") or row.get("chunk_text") or ""
        if isinstance(new_text, str) and len(new_text) > len(old_text or ""):
            current["text"] = new_text
        for key, value in row.items():
            if key in {"text", "chunk_text"}:
                continue
            if current.get(key) in (None, "", [], False) and value not in (None, "", []):
                current[key] = value
    return list(merged.values())


def _same_document_pool(
    pool: list[dict[str, Any]],
    document_id: str,
) -> list[dict[str, Any]]:
    if not document_id:
        return pool
    return [
        row
        for row in pool
        if not row.get("document_id") or str(row.get("document_id") or "") == document_id
    ]


def _localize_on_candidate(
    candidate: dict[str, Any],
    claim_text: str,
    quote: str | None,
    pdf_path: str | None,
) -> dict[str, Any] | None:
    chunk_id = str(candidate.get("chunk_id") or "")
    document_id = str(candidate.get("document_id") or "")
    if not chunk_id or not document_id:
        return None

    cleaned_quote = sanitize_quote(quote) if quote else None
    chunk_text = _candidate_text(candidate)
    if cleaned_quote and not _validate_quote_against_chunk(cleaned_quote, chunk_text):
        cleaned_quote = None

    return resolve_claim_evidence(
        document_id=document_id,
        chunk_id=chunk_id,
        claim_text=claim_text,
        quote=cleaned_quote,
        pdf_path=pdf_path,
    )


def _merge_resolved_into_source(
    base: dict[str, Any],
    resolved: dict[str, Any],
) -> dict[str, Any]:
    item = dict(base)
    item["chunk_id"] = str(resolved.get("chunk_id") or item.get("chunk_id") or "")
    status = str(resolved.get("quote_mapping_status") or "failed")
    item["quote_mapping_status"] = status
    item["quote_highlight_available"] = bool(resolved.get("quote_highlight_available"))
    item["quote_regions"] = list(resolved.get("quote_regions") or [])
    item["localization_confidence"] = float(resolved.get("localization_confidence") or 0.0)
    item["source_spans"] = list(resolved.get("source_spans") or [])
    if resolved.get("quote"):
        item["quote"] = resolved["quote"]
        item["quotes"] = [resolved["quote"]]
    page_start = resolved.get("page_start")
    if isinstance(page_start, int) and page_start >= 1:
        item["page"] = page_start
    row_source = str(resolved.get("source") or "")
    item["content_type"] = infer_content_type(
        _candidate_text(item) or _chunk_text_from_index(str(item.get("chunk_id") or "")),
        highlight_available=bool(resolved.get("highlight_available")),
        layout_source=row_source if row_source else SOURCE_NONE,
        text_engine=str(resolved.get("text_engine") or ""),
    )
    return item


def _strip_client_text(item: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(item)
    cleaned.pop("text", None)
    cleaned.pop("chunk_text", None)
    return cleaned


def _apply_text_rebind(
    bound_source: dict[str, Any],
    winner: dict[str, Any],
    *,
    retrieval_chunk_id: str,
    evidence_id: str,
) -> dict[str, Any]:
    merged = dict(bound_source)
    selected_chunk_id = str(winner.get("chunk_id") or retrieval_chunk_id)
    merged["chunk_id"] = selected_chunk_id
    if winner.get("page") is not None:
        merged["page"] = winner.get("page")
    if winner.get("document_id"):
        merged["document_id"] = winner.get("document_id")
    if winner.get("filename"):
        merged["filename"] = winner.get("filename")
    if winner.get("relevance") is not None:
        merged["relevance"] = winner.get("relevance")
    text = _candidate_text(winner)
    if text:
        merged["snippet"] = make_snippet(text)
        merged["text"] = text
    if selected_chunk_id != retrieval_chunk_id:
        merged["rebound_from_chunk_id"] = retrieval_chunk_id
        merged["rebound_from_evidence_id"] = evidence_id
        merged["anchor_evidence_id"] = _normalize_token(
            str(winner.get("evidence_id") or "")
        )
        merged["anchor_chunk_id"] = selected_chunk_id
    return merged


def _should_rebind(
    *,
    bound_chunk_id: str,
    winner_chunk_id: str,
    bound_score: float,
    winner_score: float,
    winner_status: str,
    winner_support: TextSupport,
    bound_coverage: float,
    informative: bool,
    quote_on_bound: bool,
    quote_on_winner: bool,
) -> bool:
    if not winner_chunk_id or winner_chunk_id == bound_chunk_id:
        return False
    if winner_score < bound_score + CLAIM_REBIND_MARGIN:
        return False
    if winner_score < CLAIM_SUPPORT_MIN:
        return False

    if not informative:
        if quote_on_winner and not quote_on_bound:
            return True
        if (
            float(winner_support.confidence or 0.0) >= _STRONG_REBIND_CONFIDENCE
            and bound_coverage < 0.25
        ):
            return True
        return False

    return winner_status == "supported"


def orchestrate_claim_for_evidence(
    evidence_id: str,
    bound_source: dict[str, Any],
    all_candidates: list[dict[str, Any]],
    *,
    claim_text: str,
    quote: str | None,
    pdf_path: str | None,
    localize: bool = True,
) -> OrchestrationResult:
    """
    Search recall-pool candidates for the best supporting anchor for one claim.

    E-ID stays fixed; chunk_id/page/regions may rebind to a better candidate.
    """
    claim = re.sub(r"\s+", " ", (claim_text or "").strip())
    retrieval_chunk_id = str(bound_source.get("chunk_id") or "")
    document_id = str(bound_source.get("document_id") or "")
    cleaned_quote = sanitize_quote(quote) if quote else None
    informative = is_informative_claim(claim, cleaned_quote)

    pool = _same_document_pool(list(all_candidates or []), document_id)
    if not pool:
        pool = [bound_source]

    texts = [_candidate_text(row) for row in pool]
    df = build_token_df(texts)
    n_docs = max(1, len(pool))

    scored_rows: list[dict[str, Any]] = []
    best_idx = -1
    best_score = -1.0
    bound_idx = -1

    for idx, candidate in enumerate(pool):
        cid = str(candidate.get("chunk_id") or "")
        text = _candidate_text(candidate)
        support = score_text_support(claim, text, cleaned_quote)
        coverage = claim_token_coverage(claim, text, df=df, n_docs=n_docs)
        rel = candidate.get("relevance")
        relevance = rel if isinstance(rel, int) else None
        score = _combined_score(_span_component(support), coverage, relevance)
        public_status = _public_support_status(support, coverage)
        quote_hit = bool(
            cleaned_quote and text and _validate_quote_against_chunk(cleaned_quote, text)
        )
        row = {
            "evidence_id": _normalize_token(str(candidate.get("evidence_id") or "")),
            "chunk_id": cid,
            "score": round(score, 4),
            "status": public_status,
            "support_status": public_status,
            "confidence": round(float(support.confidence or 0.0), 4),
            "coverage": round(coverage, 4),
            "quote_hit": quote_hit,
            "page": candidate.get("page"),
            "citation_eligible": bool(candidate.get("citation_eligible") or candidate.get("evidence_id")),
        }
        scored_rows.append(row)
        if cid == retrieval_chunk_id:
            bound_idx = idx
        if score > best_score:
            best_score = score
            best_idx = idx

    if best_idx < 0:
        return OrchestrationResult(
            source=_strip_client_text(dict(bound_source)),
            claim_text=claim,
            candidates_searched=scored_rows,
            rebinding_applied=False,
            retrieval_chunk_id=retrieval_chunk_id,
            selected_chunk_id=retrieval_chunk_id,
        )

    bound_row = scored_rows[bound_idx] if bound_idx >= 0 else {
        "score": 0.0,
        "coverage": 0.0,
        "quote_hit": False,
        "status": "unsupported",
    }
    winner = pool[best_idx]
    winner_row = scored_rows[best_idx]
    winner_text = _candidate_text(winner)
    winner_support = score_text_support(claim, winner_text, cleaned_quote)

    rebinding = _should_rebind(
        bound_chunk_id=retrieval_chunk_id,
        winner_chunk_id=str(winner.get("chunk_id") or ""),
        bound_score=float(bound_row.get("score") or 0.0),
        winner_score=float(winner_row.get("score") or 0.0),
        winner_status=str(winner_row.get("status") or "unsupported"),
        winner_support=winner_support,
        bound_coverage=float(bound_row.get("coverage") or 0.0),
        informative=informative,
        quote_on_bound=bool(bound_row.get("quote_hit")),
        quote_on_winner=bool(winner_row.get("quote_hit")),
    )
    selected = winner if rebinding else (
        pool[bound_idx] if bound_idx >= 0 else winner
    )
    selected_chunk_id = str(selected.get("chunk_id") or retrieval_chunk_id)
    selected_text = _candidate_text(selected)
    selected_support = score_text_support(claim, selected_text, cleaned_quote)
    selected_coverage = claim_token_coverage(
        claim, selected_text, df=df, n_docs=n_docs
    )
    support_status = _public_support_status(selected_support, selected_coverage)
    support_confidence = max(
        float(selected_support.confidence or 0.0),
        selected_coverage,
    )

    if rebinding:
        merged = _apply_text_rebind(
            bound_source,
            selected,
            retrieval_chunk_id=retrieval_chunk_id,
            evidence_id=evidence_id,
        )
    else:
        merged = dict(bound_source)

    selected_quote = cleaned_quote
    if selected_quote and not _validate_quote_against_chunk(selected_quote, selected_text):
        selected_quote = None
        merged["quote"] = None
        merged["quotes"] = []

    if localize:
        resolved = _localize_on_candidate(
            selected,
            claim,
            selected_quote,
            pdf_path,
        )
        if resolved:
            merged = _merge_resolved_into_source(merged, resolved)
            owner_id = str(resolved.get("chunk_id") or selected_chunk_id)
            if owner_id and owner_id != selected_chunk_id:
                if not rebinding:
                    merged["rebound_from_chunk_id"] = retrieval_chunk_id
                    merged["rebound_from_evidence_id"] = evidence_id
                    merged["anchor_chunk_id"] = owner_id
                rebinding = True
                selected_chunk_id = owner_id
                span = None
                spans = resolved.get("source_spans") or []
                if spans:
                    span = spans[0]
                span = span or resolved.get("quote")
                if span:
                    merged["snippet"] = make_snippet(str(span))

    merged["support_status"] = support_status
    merged["support_confidence"] = round(support_confidence, 4)
    merged["claim_context"] = claim

    return OrchestrationResult(
        source=_strip_client_text(merged),
        claim_text=claim,
        candidates_searched=scored_rows,
        rebinding_applied=rebinding,
        retrieval_chunk_id=retrieval_chunk_id,
        selected_chunk_id=selected_chunk_id,
        support_status=support_status,
        support_confidence=round(support_confidence, 4),
    )


def orchestrate_all_claims(
    answer: str,
    sources: list[dict[str, Any]] | None,
    *,
    claim_texts: dict[str, str],
    quotes_by_id: dict[str, list[str]],
    pdf_cache: dict[str, str | None],
    resolve_regions: bool = True,
    recall_candidates: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """
    Run orchestration for every source row that has a claim or quote in the answer.

    Searches the recall pool when provided; otherwise falls back to citeable sources.

    Returns enriched sources and per-evidence_id orchestration metadata for tracing.
    """
    if not sources:
        return [], {}

    by_id: dict[str, dict[str, Any]] = {}
    for source in sources:
        eid = _normalize_token(str(source.get("evidence_id") or ""))
        if eid:
            by_id[eid] = source

    meta: dict[str, dict[str, Any]] = {}
    enriched: list[dict[str, Any]] = []

    for source in sources:
        evidence_id = _normalize_token(str(source.get("evidence_id") or ""))
        if not evidence_id:
            enriched.append(dict(source))
            continue

        claim_text = claim_texts.get(evidence_id, "")
        quote_list = quotes_by_id.get(evidence_id) or list(source.get("quotes") or [])
        primary_quote = quote_list[0] if quote_list else None
        if not claim_text:
            claim_text = primary_quote or ""

        document_id = str(source.get("document_id") or "")
        pdf_path: str | None = None
        if document_id:
            if document_id not in pdf_cache:
                pdf_cache[document_id] = document_pdf_path(document_id)
            pdf_path = pdf_cache[document_id]

        if not claim_text and not primary_quote:
            enriched.append(dict(source))
            continue

        pool = _merge_candidate_pool(source, recall_candidates, sources)
        result = orchestrate_claim_for_evidence(
            evidence_id,
            source,
            pool,
            claim_text=claim_text,
            quote=primary_quote,
            pdf_path=pdf_path,
            localize=resolve_regions,
        )
        item = dict(result.source)
        selected_text = _candidate_text(_pool_row(pool, result.selected_chunk_id))
        kept_quotes = [
            q
            for q in quote_list
            if selected_text and _validate_quote_against_chunk(q, selected_text)
        ]
        if kept_quotes:
            item["quotes"] = kept_quotes
            item["quote"] = kept_quotes[0]
        elif result.rebinding_applied:
            item["quotes"] = []
            item["quote"] = None
        elif quote_list:
            item["quotes"] = quote_list
            if not item.get("quote"):
                item["quote"] = quote_list[0]
        item["claim_context"] = result.claim_text
        if len(item.get("quotes") or []) > 1:
            item["additional_quotes"] = item["quotes"][1:]
        item["support_status"] = result.support_status
        item["support_confidence"] = result.support_confidence
        meta[evidence_id] = {
            "claim_text": result.claim_text,
            "candidates_searched": result.candidates_searched,
            "rebinding_applied": result.rebinding_applied,
            "retrieval_chunk_id": result.retrieval_chunk_id,
            "selected_chunk_id": result.selected_chunk_id,
            "support_status": result.support_status,
            "support_confidence": result.support_confidence,
        }
        enriched.append(item)
        by_id[evidence_id] = item

    return enriched, meta


def _pool_row(pool: list[dict[str, Any]], chunk_id: Any) -> dict[str, Any]:
    target = str(chunk_id or "")
    for row in pool:
        if str(row.get("chunk_id") or "") == target:
            return row
    return {}
