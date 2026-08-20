"""Query-time quote → PDF span mapping. Does not change stored chunk_evidence."""

from __future__ import annotations

from typing import Any

from citation_resolver import sanitize_quote
from database.evidence_store import get_chunk_evidence
from evidence_mapping import (
    extract_page_layouts,
    map_quote_to_regions,
)


def _chunk_text_from_chroma(chunk_id: str) -> str | None:
    from rag import get_collection

    collection = get_collection()
    payload = collection.get(ids=[chunk_id], include=["documents"])
    documents = payload.get("documents") or []
    if not documents:
        return None
    text = documents[0]
    return text if isinstance(text, str) else None


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


def public_chunk_evidence(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": row["chunk_id"],
        "document_id": row["document_id"],
        "page_start": row["page_start"],
        "page_end": row["page_end"],
        "snippet": row.get("snippet") or "",
        "highlight_available": bool(row.get("highlight_available")),
        "regions": _public_regions(row.get("regions")),
        "quote": None,
        "quote_highlight_available": False,
        "quote_regions": [],
        "quote_mapping_status": "none",
    }


def resolve_quote_evidence(
    *,
    document_id: str,
    chunk_id: str,
    quote: str | None,
    pdf_path: str | None,
) -> dict[str, Any] | None:
    row = get_chunk_evidence(chunk_id)
    if not row or row.get("document_id") != document_id:
        return None

    payload = public_chunk_evidence(row)
    raw_quote = (quote or "").strip()
    cleaned = sanitize_quote(raw_quote) if raw_quote else None
    payload["quote"] = cleaned
    if raw_quote and not cleaned:
        payload["quote_mapping_status"] = "rejected"
        return payload
    if not cleaned:
        return payload

    chunk_text = _chunk_text_from_chroma(chunk_id) or ""
    pages = set(range(int(row["page_start"]), int(row["page_end"]) + 1))
    for item in row.get("ranges") or []:
        if isinstance(item, dict) and item.get("page") is not None:
            try:
                pages.add(int(item["page"]))
            except (TypeError, ValueError):
                continue

    layouts = {}
    if pdf_path:
        try:
            layouts = extract_page_layouts(pdf_path, page_numbers=pages)
        except Exception:
            layouts = {}

    mapped = map_quote_to_regions(
        cleaned,
        chunk_text=chunk_text,
        layouts=layouts,
        page_start=int(row["page_start"]),
        page_end=int(row["page_end"]),
        ranges=row.get("ranges") or [],
    )
    status = str(mapped.get("match_type") or "failed")
    quote_regions = (
        _public_regions(mapped.get("regions"))
        if mapped.get("quote_highlight_available")
        else []
    )
    mapped_ok = bool(mapped.get("quote_highlight_available") and quote_regions)
    payload["quote_highlight_available"] = mapped_ok
    payload["quote_regions"] = quote_regions if mapped_ok else []
    if mapped_ok:
        payload["quote_mapping_status"] = status
    elif status in {"not_in_chunk", "no_layout", "not_on_page", "failed"}:
        payload["quote_mapping_status"] = status
    else:
        payload["quote_mapping_status"] = "failed"
    if mapped_ok and mapped.get("pages"):
        payload["page_start"] = min(mapped["pages"])
        payload["page_end"] = max(mapped["pages"])
    return payload
