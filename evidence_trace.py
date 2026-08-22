"""
Production observability for the claim → evidence → PDF → UI pipeline.

Emits structured traces (logging + optional payload attachment) so every answer
can be diagnosed without reproducing the user session.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from citation_resolver import _RESOLVED_MARKER_RE, _normalize_token, sanitize_quote

logger = logging.getLogger(__name__)

_TRACE_VERSION = 1


@dataclass
class CandidateSnapshot:
    evidence_id: str
    chunk_id: str
    document_id: str
    page: int | None
    relevance: int | None


@dataclass
class ClaimTrace:
    evidence_id: str
    claim_text: str
    marker_quote: str | None
    # Retrieval slot (E# assignment at retrieve time)
    retrieval_evidence_id: str
    retrieval_chunk_id: str
    retrieval_page: int | None
    # Selected anchor (may differ after orchestration)
    selected_chunk_id: str
    selected_page: int | None
    rebinding_applied: bool
    candidates_searched: list[dict[str, Any]] = field(default_factory=list)
    localization_status: str = "none"
    localization_confidence: float = 0.0
    support_status: str = "unknown"
    support_confidence: float = 0.0
    source_spans: list[str] = field(default_factory=list)
    region_count: int = 0
    highlight_pages: list[int] = field(default_factory=list)
    quote_highlight_available: bool = False
    ui_status: str = "unknown"
    in_final_citations: bool = False
    in_answer_marker: bool = True


@dataclass
class EvidenceAnswerTrace:
    version: int = _TRACE_VERSION
    retrieval_candidates: list[dict[str, Any]] = field(default_factory=list)
    claims: list[ClaimTrace] = field(default_factory=list)
    markers_in_answer: list[str] = field(default_factory=list)
    markers_missing_citation: list[str] = field(default_factory=list)
    final_citation_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "retrieval_candidates": self.retrieval_candidates,
            "claims": [asdict(c) for c in self.claims],
            "markers_in_answer": self.markers_in_answer,
            "markers_missing_citation": self.markers_missing_citation,
            "final_citation_ids": self.final_citation_ids,
        }


def _markers_in_answer(answer: str) -> list[str]:
    order: list[str] = []
    seen: set[str] = set()
    for match in _RESOLVED_MARKER_RE.finditer(answer or ""):
        evidence_id = _normalize_token(match.group(1) or "")
        if evidence_id and evidence_id not in seen:
            seen.add(evidence_id)
            order.append(evidence_id)
    return order


def _marker_quotes(answer: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for match in _RESOLVED_MARKER_RE.finditer(answer or ""):
        evidence_id = _normalize_token(match.group(1) or "")
        if not evidence_id:
            continue
        raw = match.group(2)
        out[evidence_id] = sanitize_quote(raw) if raw else None
    return out


def ui_status_for_source(source: dict[str, Any], in_final: bool = True) -> str:
    if not in_final:
        return "citation_dropped"
    status = str(source.get("quote_mapping_status") or "none")
    if source.get("quote_highlight_available"):
        return "highlight_ok"
    if status in {"fallback_chunk", "unresolved", "no_evidence_data", "no_layout"}:
        return f"fallback_{status}"
    if status in {"not_in_chunk", "rejected", "failed"}:
        return f"invalid_{status}"
    if status in {"exact", "sentence", "semantic_span", "normalized", "fuzzy_compact"}:
        return "snippet_only"
    return "snippet_only"


def snapshot_retrieval_candidates(sources: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in sources or []:
        evidence_id = _normalize_token(str(source.get("evidence_id") or "")) or ""
        rows.append(
            {
                "evidence_id": evidence_id,
                "chunk_id": str(source.get("chunk_id") or ""),
                "document_id": str(source.get("document_id") or ""),
                "page": source.get("page"),
                "relevance": source.get("relevance"),
            }
        )
    return rows


def build_evidence_trace(
    answer: str,
    retrieved_sources: list[dict[str, Any]] | None,
    enriched_sources: list[dict[str, Any]] | None,
    final_sources: list[dict[str, Any]] | None,
    *,
    claim_texts: dict[str, str] | None = None,
    orchestration_meta: dict[str, dict[str, Any]] | None = None,
) -> EvidenceAnswerTrace:
    """
    Build a full trace after finalize + used_sources.

    orchestration_meta: optional per evidence_id dict from claim orchestrator
      (candidates_searched, rebinding_applied, retrieval_chunk_id, ...)
    """
    trace = EvidenceAnswerTrace(
        retrieval_candidates=snapshot_retrieval_candidates(retrieved_sources),
        markers_in_answer=_markers_in_answer(answer),
    )
    marker_quotes = _marker_quotes(answer)
    enriched_by_id = {
        _normalize_token(str(s.get("evidence_id") or "")): s
        for s in (enriched_sources or [])
        if s.get("evidence_id")
    }
    final_by_id = {
        _normalize_token(str(s.get("evidence_id") or "")): s
        for s in (final_sources or [])
        if s.get("evidence_id")
    }
    retrieval_by_id = {
        _normalize_token(str(s.get("evidence_id") or "")): s
        for s in (retrieved_sources or [])
        if s.get("evidence_id")
    }

    trace.final_citation_ids = list(final_by_id.keys())

    for evidence_id in trace.markers_in_answer:
        retrieval = retrieval_by_id.get(evidence_id) or {}
        enriched = enriched_by_id.get(evidence_id) or final_by_id.get(evidence_id) or {}
        in_final = evidence_id in final_by_id
        meta = (orchestration_meta or {}).get(evidence_id) or {}

        regions = enriched.get("quote_regions") or []
        pages = sorted(
            {
                int(r["page"])
                for r in regions
                if isinstance(r, dict) and r.get("page") is not None
            }
        )

        retrieval_chunk = str(
            meta.get("retrieval_chunk_id") or retrieval.get("chunk_id") or enriched.get("chunk_id") or ""
        )
        selected_chunk = str(enriched.get("chunk_id") or retrieval_chunk)

        claim_trace = ClaimTrace(
            evidence_id=evidence_id,
            claim_text=(claim_texts or {}).get(evidence_id, "") or meta.get("claim_text", ""),
            marker_quote=marker_quotes.get(evidence_id),
            retrieval_evidence_id=evidence_id,
            retrieval_chunk_id=retrieval_chunk,
            retrieval_page=retrieval.get("page"),
            selected_chunk_id=selected_chunk,
            selected_page=enriched.get("page"),
            rebinding_applied=bool(meta.get("rebinding_applied"))
            or (retrieval_chunk and selected_chunk and retrieval_chunk != selected_chunk),
            candidates_searched=list(meta.get("candidates_searched") or []),
            localization_status=str(enriched.get("quote_mapping_status") or "none"),
            localization_confidence=float(enriched.get("localization_confidence") or 0.0),
            support_status=str(
                enriched.get("support_status")
                or meta.get("support_status")
                or "unknown"
            ),
            support_confidence=float(
                enriched.get("support_confidence")
                if enriched.get("support_confidence") is not None
                else meta.get("support_confidence") or 0.0
            ),
            source_spans=list(enriched.get("source_spans") or []),
            region_count=len(regions),
            highlight_pages=pages,
            quote_highlight_available=bool(enriched.get("quote_highlight_available")),
            ui_status=ui_status_for_source(enriched, in_final),
            in_final_citations=in_final,
            in_answer_marker=True,
        )
        trace.claims.append(claim_trace)

        if not in_final:
            trace.markers_missing_citation.append(evidence_id)

    return trace


def log_evidence_trace(
    trace: EvidenceAnswerTrace,
    *,
    conversation_id: str | None = None,
    question: str | None = None,
) -> None:
    payload = trace.to_dict()
    if conversation_id:
        payload["conversation_id"] = conversation_id
    if question:
        payload["question_preview"] = (question or "")[:200]
    try:
        logger.info("evidence_trace %s", json.dumps(payload, default=str))
    except Exception:
        logger.info("evidence_trace version=%s claims=%s", trace.version, len(trace.claims))


def attach_trace_dict_to_sources(
    sources: list[dict[str, Any]] | None,
    trace_dict: dict[str, Any],
) -> list[dict[str, Any]]:
    """Attach per-claim trace from a serialized trace payload."""
    claims = trace_dict.get("claims") or []
    by_id = {
        str(c.get("evidence_id") or "").upper(): c
        for c in claims
        if isinstance(c, dict) and c.get("evidence_id")
    }
    out: list[dict[str, Any]] = []
    for source in sources or []:
        item = dict(source)
        evidence_id = _normalize_token(str(item.get("evidence_id") or ""))
        claim_trace = by_id.get(evidence_id)
        if claim_trace:
            item["ui_status"] = claim_trace.get("ui_status")
            item["evidence_trace"] = {
                "retrieval_chunk_id": claim_trace.get("retrieval_chunk_id"),
                "selected_chunk_id": claim_trace.get("selected_chunk_id"),
                "rebinding_applied": claim_trace.get("rebinding_applied"),
                "localization_status": claim_trace.get("localization_status"),
                "localization_confidence": claim_trace.get("localization_confidence"),
                "support_status": claim_trace.get("support_status"),
                "support_confidence": claim_trace.get("support_confidence"),
                "ui_status": claim_trace.get("ui_status"),
                "highlight_pages": claim_trace.get("highlight_pages"),
                "region_count": claim_trace.get("region_count"),
            }
        out.append(item)
    return out
