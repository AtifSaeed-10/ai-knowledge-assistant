"""
Deterministic claim ↔ citation ↔ quote ↔ chunk ↔ PDF region validation.

The LLM output is untrusted. This module verifies markers against retrieved
evidence and enriches citation payloads before they reach the client.
"""

from __future__ import annotations

import re
from typing import Any

from citation_resolver import (
    _RESOLVED_MARKER_RE,
    _normalize_token,
    format_citation_marker,
    quotes_by_evidence_id,
    resolve_evidence_markers,
    sanitize_quote,
    valid_ids_from_sources,
)
from document_paths import document_pdf_path
from evidence_mapping import compact_contains
from quote_evidence import resolve_quote_evidence
from answer_formatter import polish_answer_text

# Marker with optional quote — used for repair passes.
_QUOTED_MARKER_RE = re.compile(
    r"\[(E[1-9]\d*)(?:\:\s*\"([^\"\]]*)\")?\]",
    re.IGNORECASE,
)


def _source_by_evidence_id(sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for source in sources or []:
        evidence_id = _normalize_token(str(source.get("evidence_id") or ""))
        if evidence_id:
            out[evidence_id] = source
    return out


def _chunk_text_for_source(source: dict[str, Any]) -> str:
    chunk_id = source.get("chunk_id")
    if not chunk_id:
        return ""
    from rag import get_collection

    payload = get_collection().get(ids=[str(chunk_id)], include=["documents"])
    documents = payload.get("documents") or []
    if not documents:
        return ""
    text = documents[0]
    return text if isinstance(text, str) else ""


def validate_quote_against_chunk(quote: str, chunk_text: str) -> bool:
    cleaned = sanitize_quote(quote)
    if not cleaned:
        return False
    return compact_contains(chunk_text or "", cleaned)


def _public_regions(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in rows or []:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "page": item.get("page"),
                "x0": item.get("x0"),
                "y0": item.get("y0"),
                "x1": item.get("x1"),
                "y1": item.get("y1"),
                "coord_space": item.get("coord_space"),
            }
        )
    return out


def enrich_source_with_quote_evidence(
    source: dict[str, Any],
    *,
    quote: str | None,
    pdf_path: str | None = None,
) -> dict[str, Any]:
    """Validate quote and attach pre-resolved highlight metadata to one source."""
    item = dict(source)
    cleaned = sanitize_quote(quote) if quote else None
    item["quote"] = cleaned
    item["quotes"] = [cleaned] if cleaned else []
    item["quote_mapping_status"] = "none"
    item["quote_highlight_available"] = False
    item["quote_regions"] = []

    if not cleaned:
        return item

    chunk_id = str(item.get("chunk_id") or "")
    document_id = str(item.get("document_id") or "")
    if not chunk_id or not document_id:
        item["quote_mapping_status"] = "failed"
        return item

    chunk_text = _chunk_text_for_source(item)
    if not validate_quote_against_chunk(cleaned, chunk_text):
        item["quote"] = None
        item["quotes"] = []
        item["quote_mapping_status"] = "not_in_chunk"
        return item

    path = pdf_path if pdf_path is not None else document_pdf_path(document_id)
    resolved = resolve_quote_evidence(
        document_id=document_id,
        chunk_id=chunk_id,
        quote=cleaned,
        pdf_path=path,
    )
    if not resolved:
        item["quote_mapping_status"] = "failed"
        return item

    status = str(resolved.get("quote_mapping_status") or "failed")
    item["quote_mapping_status"] = status
    item["quote_highlight_available"] = bool(resolved.get("quote_highlight_available"))
    item["quote_regions"] = _public_regions(resolved.get("quote_regions"))
    if resolved.get("quote"):
        item["quote"] = resolved["quote"]
    page_start = resolved.get("page_start")
    if isinstance(page_start, int) and page_start >= 1:
        item["page"] = page_start
    return item


def repair_answer_markers(answer: str, sources: list[dict[str, Any]]) -> str:
    """
    Downgrade invalid quotes to bare [E#] markers; drop unknown E-IDs.
    """
    valid_ids = valid_ids_from_sources(sources)
    by_id = _source_by_evidence_id(sources)

    def replace(match: re.Match[str]) -> str:
        evidence_id = _normalize_token(match.group(1) or "")
        raw_quote = match.group(2)
        if not evidence_id or evidence_id not in valid_ids:
            return ""
        if raw_quote is None:
            return format_citation_marker(evidence_id)
        quote = sanitize_quote(raw_quote)
        if not quote:
            return format_citation_marker(evidence_id)
        source = by_id.get(evidence_id) or {}
        chunk_text = _chunk_text_for_source(source)
        if not validate_quote_against_chunk(quote, chunk_text):
            return format_citation_marker(evidence_id)
        return format_citation_marker(evidence_id, quote)

    repaired = _QUOTED_MARKER_RE.sub(replace, answer or "")
    return resolve_evidence_markers(repaired, valid_ids)


def attach_all_quotes_to_sources(
    sources: list[dict[str, Any]] | None,
    text: str,
) -> list[dict[str, Any]]:
    quotes = quotes_by_evidence_id(text)
    attached: list[dict[str, Any]] = []
    for source in sources or []:
        item = dict(source)
        evidence_id = _normalize_token(str(item.get("evidence_id") or ""))
        used = quotes.get(evidence_id or "") or []
        item["quotes"] = used
        item["quote"] = used[0] if used else None
        attached.append(item)
    return attached


def finalize_answer_citations(
    answer: str,
    sources: list[dict[str, Any]] | None,
    *,
    resolve_regions: bool = True,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Validate quotes, repair answer markers, enrich sources with mapping status
    and optional pre-resolved PDF regions.
    """
    valid_ids = valid_ids_from_sources(sources)
    cleaned = polish_answer_text(answer or "")
    resolved = resolve_evidence_markers(cleaned, valid_ids)
    with_quotes = attach_all_quotes_to_sources(sources, resolved)
    repaired = repair_answer_markers(resolved, with_quotes)
    by_id = _source_by_evidence_id(with_quotes)

    enriched: list[dict[str, Any]] = []
    pdf_cache: dict[str, str | None] = {}

    for source in with_quotes:
        evidence_id = _normalize_token(str(source.get("evidence_id") or ""))
        quote_list = list(source.get("quotes") or [])
        primary_quote = quote_list[0] if quote_list else None

        document_id = str(source.get("document_id") or "")
        pdf_path: str | None = None
        if resolve_regions and document_id:
            if document_id not in pdf_cache:
                pdf_cache[document_id] = document_pdf_path(document_id)
            pdf_path = pdf_cache[document_id]

        if primary_quote:
            chunk_text = _chunk_text_for_source(source)
            if not validate_quote_against_chunk(primary_quote, chunk_text):
                item = dict(source)
                item["quote"] = None
                item["quotes"] = []
                item["quote_mapping_status"] = "not_in_chunk"
                item["quote_highlight_available"] = False
                item["quote_regions"] = []
            elif resolve_regions:
                item = enrich_source_with_quote_evidence(
                    source,
                    quote=primary_quote,
                    pdf_path=pdf_path,
                )
                item["quotes"] = quote_list
                if len(quote_list) > 1:
                    item["additional_quotes"] = quote_list[1:]
            else:
                item = dict(source)
                item["quote"] = primary_quote
                item["quotes"] = quote_list
                item["quote_mapping_status"] = "none"
                item["quote_highlight_available"] = False
                item["quote_regions"] = []
        else:
            item = dict(source)
            item.setdefault("quotes", quote_list)
            item.setdefault("quote_mapping_status", "none")
            item.setdefault("quote_highlight_available", False)
            item.setdefault("quote_regions", [])

        enriched.append(item)
        if evidence_id:
            by_id[evidence_id] = item

    return repaired, enriched


def used_sources(sources: list[dict[str, Any]], answer: str) -> list[dict[str, Any]]:
    """Keep only sources whose evidence id appears in the validated answer."""
    valid_ids = valid_ids_from_sources(sources)
    order: list[str] = []
    present: set[str] = set()
    for match in _RESOLVED_MARKER_RE.finditer(answer or ""):
        evidence_id = _normalize_token(match.group(1) or "")
        if evidence_id in valid_ids and evidence_id not in present:
            present.add(evidence_id)
            order.append(evidence_id)
    by_id = _source_by_evidence_id(sources)
    return [by_id[evidence_id] for evidence_id in order if evidence_id in by_id]
