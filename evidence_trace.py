"""
Production observability for the claim → evidence → PDF → UI pipeline.

Every finalized answer gets a correlation id and a structured trace so we can
follow: retrieval slot → recall candidates → selected chunk → localization →
PDF regions → UI status. Passage text is never written into the log.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from citation_resolver import _RESOLVED_MARKER_RE, _normalize_token, sanitize_quote
from visual_evidence import SCAN_TYPES, TYPE_FIGURE_CAPTION, TYPE_TABLE, VISUAL_TYPES

logger = logging.getLogger(__name__)

_TRACE_VERSION = 1
_QUESTION_PREVIEW = 200
_MAX_SEARCHED_ROWS = 12

_CANDIDATE_KEYS = (
    "evidence_id",
    "chunk_id",
    "document_id",
    "page",
    "score",
    "status",
    "support_status",
    "confidence",
    "coverage",
    "quote_hit",
    "citation_eligible",
    "relevance",
)


@dataclass
class ClaimTrace:
    evidence_id: str
    claim_text: str
    marker_quote: str | None
    retrieval_evidence_id: str
    retrieval_chunk_id: str
    retrieval_page: int | None
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
    content_type: str = "native_text"
    evidence_state: str | None = None
    citation_eligible: bool | None = None
    ui_status: str = "unknown"
    in_final_citations: bool = False
    in_answer_marker: bool = True


@dataclass
class EvidenceAnswerTrace:
    version: int = _TRACE_VERSION
    trace_id: str = ""
    retrieval_candidates: list[dict[str, Any]] = field(default_factory=list)
    recall_candidates: list[dict[str, Any]] = field(default_factory=list)
    claims: list[ClaimTrace] = field(default_factory=list)
    markers_in_answer: list[str] = field(default_factory=list)
    markers_missing_citation: list[str] = field(default_factory=list)
    final_citation_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "trace_id": self.trace_id,
            "retrieval_candidates": self.retrieval_candidates,
            "recall_candidates": self.recall_candidates,
            "claims": [asdict(claim) for claim in self.claims],
            "markers_in_answer": self.markers_in_answer,
            "markers_missing_citation": self.markers_missing_citation,
            "final_citation_ids": self.final_citation_ids,
        }


def _new_trace_id() -> str:
    return uuid.uuid4().hex[:16]


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


def _meta_first(meta: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in meta and meta[key] not in (None, ""):
            return meta[key]
    return default


def _compact_row(row: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    out: dict[str, Any] = {}
    for key in _CANDIDATE_KEYS:
        if key in row and row[key] is not None:
            out[key] = row[key]
    if "chunk_id" not in out and row.get("id"):
        out["chunk_id"] = row.get("id")
    return out


def _compact_rows(
    rows: list[Any] | None,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in rows or []:
        if not isinstance(item, dict):
            continue
        compact.append(_compact_row(item))
        if limit is not None and len(compact) >= limit:
            break
    return compact


def ui_status_for_source(source: dict[str, Any], in_final: bool = True) -> str:
    if not in_final:
        return "citation_dropped"
    if source.get("quote_highlight_available"):
        return "highlight_ok"
    status = str(source.get("quote_mapping_status") or "none")
    if status in {"fallback_chunk", "unresolved", "no_evidence_data", "no_layout"}:
        return f"fallback_{status}"
    if status in {"not_in_chunk", "rejected", "failed"}:
        return f"invalid_{status}"
    kind = str(source.get("content_type") or "").strip()
    if kind in VISUAL_TYPES:
        if kind in SCAN_TYPES:
            return "page_only_scan"
        if kind in {TYPE_FIGURE_CAPTION, TYPE_TABLE}:
            return "page_only_visual"
    return "snippet_only"


def snapshot_retrieval_candidates(
    sources: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
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
                "citation_eligible": source.get("citation_eligible"),
                "evidence_state": source.get("evidence_state"),
            }
        )
    return rows


def snapshot_recall_candidates(
    candidates: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Compact recall-pool rows: ids, pages, scores. No passage text."""
    return _compact_rows(candidates)


def build_evidence_trace(
    answer: str,
    retrieved_sources: list[dict[str, Any]] | None,
    enriched_sources: list[dict[str, Any]] | None,
    final_sources: list[dict[str, Any]] | None,
    *,
    claim_texts: dict[str, str] | None = None,
    orchestration_meta: dict[str, dict[str, Any]] | None = None,
    recall_candidates: list[dict[str, Any]] | None = None,
    trace_id: str | None = None,
) -> EvidenceAnswerTrace:
    """
    Build a full trace after finalize + used_sources.

    orchestration_meta accepts live orchestrator keys (candidates_searched,
    rebinding_applied) and the older aliases used in tests.
    """
    trace = EvidenceAnswerTrace(
        trace_id=trace_id or _new_trace_id(),
        retrieval_candidates=snapshot_retrieval_candidates(retrieved_sources),
        recall_candidates=snapshot_recall_candidates(recall_candidates),
        markers_in_answer=_markers_in_answer(answer),
    )
    marker_quotes = _marker_quotes(answer)
    enriched_by_id = {
        _normalize_token(str(source.get("evidence_id") or "")): source
        for source in (enriched_sources or [])
        if source.get("evidence_id")
    }
    final_by_id = {
        _normalize_token(str(source.get("evidence_id") or "")): source
        for source in (final_sources or [])
        if source.get("evidence_id")
    }
    retrieval_by_id = {
        _normalize_token(str(source.get("evidence_id") or "")): source
        for source in (retrieved_sources or [])
        if source.get("evidence_id")
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
                int(region["page"])
                for region in regions
                if isinstance(region, dict) and region.get("page") is not None
            }
        )
        retrieval_chunk = str(
            _meta_first(meta, "retrieval_chunk_id", "retrieval_chunk_id")
            or retrieval.get("chunk_id")
            or enriched.get("chunk_id")
            or ""
        )
        selected_chunk = str(
            _meta_first(meta, "selected_chunk_id", "selected_chunk_id")
            or enriched.get("chunk_id")
            or retrieval_chunk
        )
        rebinding = bool(
            _meta_first(meta, "rebinding_applied", "rebinding_applied", default=False)
        ) or bool(
            retrieval_chunk and selected_chunk and retrieval_chunk != selected_chunk
        )
        searched = _compact_rows(
            list(
                _meta_first(
                    meta,
                    "candidates_searched",
                    "candidates_searched",
                    default=[],
                )
                or []
            ),
            limit=_MAX_SEARCHED_ROWS,
        )

        trace.claims.append(
            ClaimTrace(
                evidence_id=evidence_id,
                claim_text=(claim_texts or {}).get(evidence_id, "")
                or str(meta.get("claim_text") or ""),
                marker_quote=marker_quotes.get(evidence_id),
                retrieval_evidence_id=evidence_id,
                retrieval_chunk_id=retrieval_chunk,
                retrieval_page=retrieval.get("page"),
                selected_chunk_id=selected_chunk,
                selected_page=enriched.get("page"),
                rebinding_applied=rebinding,
                candidates_searched=searched,
                localization_status=str(
                    enriched.get("quote_mapping_status") or "none"
                ),
                localization_confidence=float(
                    enriched.get("localization_confidence") or 0.0
                ),
                support_status=str(
                    enriched.get("support_status")
                    or _meta_first(meta, "support_status", "support_status")
                    or "unknown"
                ),
                support_confidence=float(
                    enriched.get("support_confidence")
                    if enriched.get("support_confidence") is not None
                    else _meta_first(
                        meta, "support_confidence", "support_confidence"
                    )
                    or 0.0
                ),
                source_spans=list(enriched.get("source_spans") or []),
                region_count=len(regions) if isinstance(regions, list) else 0,
                highlight_pages=pages,
                quote_highlight_available=bool(
                    enriched.get("quote_highlight_available")
                ),
                content_type=str(enriched.get("content_type") or "native_text"),
                evidence_state=str(enriched.get("evidence_state") or "") or None,
                citation_eligible=(
                    bool(enriched["citation_eligible"])
                    if "citation_eligible" in enriched
                    else None
                ),
                ui_status=ui_status_for_source(enriched, in_final),
                in_final_citations=in_final,
                in_answer_marker=True,
            )
        )
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
    payload["conversation_id"] = conversation_id or ""
    payload["question_preview"] = (question or "")[:_QUESTION_PREVIEW]
    try:
        logger.info("evidence_trace %s", json.dumps(payload, default=str))
    except Exception:
        logger.info(
            "evidence_trace id=%s version=%s claims=%s",
            trace.trace_id,
            trace.version,
            len(trace.claims),
        )


def attach_trace_dict_to_sources(
    sources: list[dict[str, Any]] | None,
    trace_dict: dict[str, Any],
) -> list[dict[str, Any]]:
    """Attach a compact per-claim trace (no passage text) onto citation sources."""
    claims = trace_dict.get("claims") or []
    by_id = {
        str(claim.get("evidence_id") or "").upper(): claim
        for claim in claims
        if isinstance(claim, dict) and claim.get("evidence_id")
    }
    trace_id = str(trace_dict.get("trace_id") or "")
    out: list[dict[str, Any]] = []
    for source in sources or []:
        item = dict(source)
        evidence_id = _normalize_token(str(item.get("evidence_id") or ""))
        claim_trace = by_id.get(evidence_id) if evidence_id else None
        if claim_trace:
            item["ui_status"] = claim_trace.get("ui_status")
            item["evidence_trace"] = {
                "trace_id": trace_id,
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
                "content_type": claim_trace.get("content_type"),
                "candidates_searched_count": len(
                    claim_trace.get("candidates_searched") or []
                ),
            }
        elif trace_id:
            item.setdefault("evidence_trace", {"trace_id": trace_id})
        out.append(item)
    return out
