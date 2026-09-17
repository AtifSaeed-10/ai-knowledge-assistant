"""
Citation identity vs UI evidence state.

Every recall-pool chunk sent to the LLM gets a stable E#. Citeability is a
separate UI state: high-relevance allowlisted chunks are citeable; the rest
are page_only. Grounded answers must not drop overlapping evidence just because
the model omitted a marker or relevance is below CITATION_MIN_RELEVANCE.
"""

from __future__ import annotations

from typing import Any

from answer_prompt import (
    INSUFFICIENT_CONTEXT_PHRASE,
    MISSING_EXAMPLE_PHRASE,
    MISSING_IN_DOCUMENT_PHRASE,
)
from claim_localizer import claim_token_coverage
from config import CITATION_MIN_RELEVANCE

STATE_CITEABLE = "citeable"
STATE_PAGE_ONLY = "page_only"

SUPPORT_MIN_COVERAGE = 0.12
FALLBACK_MAX_SOURCES = 3

_REFUSAL_SNIPPETS = tuple(
    phrase.lower()
    for phrase in (
        INSUFFICIENT_CONTEXT_PHRASE,
        MISSING_IN_DOCUMENT_PHRASE,
        MISSING_EXAMPLE_PHRASE,
        "no relevant information found in the document",
        "no relevant information",
        "couldn't find",
        "could not find",
        "don't have enough information",
        "do not have enough information",
        "not in the provided document",
        "not in the provided context",
        "i couldn't locate",
        "i could not locate",
    )
    if phrase
)


def evidence_state_for_chunk(
    *,
    relevance: int,
    citation_eligible: bool,
    allowlisted: bool,
) -> str:
    """Citeable only when retrieval eligibility, allowlist, and the floor all pass."""
    if (
        citation_eligible
        and allowlisted
        and int(relevance) >= CITATION_MIN_RELEVANCE
    ):
        return STATE_CITEABLE
    return STATE_PAGE_ONLY


def looks_like_evidence_refusal(answer: str) -> bool:
    """True when the answer is a grounded 'not found' / insufficient-context refusal."""
    text = (answer or "").strip().lower()
    if not text:
        return True
    return any(snippet in text for snippet in _REFUSAL_SNIPPETS)


def _text_by_chunk_id(
    recall_candidates: list[dict[str, Any]] | None,
) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in recall_candidates or []:
        chunk_id = str(row.get("chunk_id") or "")
        if not chunk_id:
            continue
        text = row.get("text") or row.get("chunk_text") or ""
        if isinstance(text, str) and text.strip():
            out[chunk_id] = text
    return out


def _support_blob(
    source: dict[str, Any],
    text_by_chunk: dict[str, str],
) -> str:
    chunk_id = str(source.get("chunk_id") or "")
    parts = [
        text_by_chunk.get(chunk_id) or "",
        source.get("text") or "",
        source.get("snippet") or "",
        source.get("quote") or "",
    ]
    return " ".join(part for part in parts if isinstance(part, str) and part.strip())


def source_supports_answer(
    answer: str,
    source: dict[str, Any],
    *,
    text_by_chunk: dict[str, str] | None = None,
) -> bool:
    blob = _support_blob(source, text_by_chunk or {})
    if not blob.strip() or not (answer or "").strip():
        return False
    return claim_token_coverage(answer, blob) >= SUPPORT_MIN_COVERAGE


def _as_page_only(source: dict[str, Any]) -> dict[str, Any]:
    item = dict(source)
    item["evidence_state"] = STATE_PAGE_ONLY
    if not item.get("ui_status"):
        item["ui_status"] = "snippet_only"
    return item


def visible_sources(
    sources: list[dict[str, Any]] | None,
    answer: str,
    *,
    recall_candidates: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Sources the UI should show for this answer.

    Cited markers win. A refusal shows nothing. A grounded answer with no
    markers keeps overlapping recall chunks as page_only (capped).
    """
    from claim_validator import used_sources

    pool = list(sources or [])
    cited = used_sources(pool, answer)
    if cited:
        return cited
    if looks_like_evidence_refusal(answer):
        return []

    text_by_chunk = _text_by_chunk_id(recall_candidates)
    supported = [
        source
        for source in pool
        if source_supports_answer(answer, source, text_by_chunk=text_by_chunk)
    ]
    supported.sort(key=lambda item: int(item.get("relevance") or 0), reverse=True)
    return [_as_page_only(source) for source in supported[:FALLBACK_MAX_SOURCES]]
