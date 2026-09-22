"""Query-time quote → PDF span mapping. Does not change stored chunk_evidence."""

from __future__ import annotations

from typing import Any

from citation_resolver import sanitize_quote
from claim_localizer import (
    STATUS_UNRESOLVED,
    localization_cache_key,
)
from claim_reanchor import (
    ReanchorWindow,
    neighbor_chunk_ids,
    reanchor_claim,
)
from config import REANCHOR_NEIGHBOR_RADIUS
from database.evidence_store import (
    get_chunk_evidence,
    get_quote_region_cache,
    upsert_quote_region_cache,
)
from document_paths import document_pdf_path
from evidence_mapping import (
    compact_contains,
    extract_page_layouts,
    infer_content_type,
    make_snippet,
    map_quote_to_regions,
    SOURCE_NONE,
)
from visual_evidence import apply_visual_highlight_policy


def _chunk_record_from_chroma(chunk_id: str) -> tuple[str | None, dict[str, Any]]:
    from rag import get_collection

    collection = get_collection()
    payload = collection.get(ids=[chunk_id], include=["documents", "metadatas"])
    documents = payload.get("documents") or []
    metadatas = payload.get("metadatas") or []
    if not documents:
        return None, {}
    text = documents[0]
    if not isinstance(text, str):
        return None, {}
    meta = metadatas[0] if metadatas else {}
    return text, meta if isinstance(meta, dict) else {}


def _chunk_text_from_chroma(chunk_id: str) -> str | None:
    text, _meta = _chunk_record_from_chroma(chunk_id)
    return text


def _chunk_meta_from_chroma(chunk_id: str) -> dict[str, Any]:
    _text, meta = _chunk_record_from_chroma(chunk_id)
    return meta


def _page_bounds(meta: dict[str, Any]) -> tuple[int, int]:
    page = meta.get("page_number")
    if page is None:
        page = meta.get("page_start")
    if page is None:
        page = meta.get("page_end")
    try:
        page_int = int(page)
    except (TypeError, ValueError):
        page_int = 1
    if page_int < 1:
        page_int = 1
    page_end = meta.get("page_end")
    try:
        page_end_int = int(page_end) if page_end is not None else page_int
    except (TypeError, ValueError):
        page_end_int = page_int
    if page_end_int < page_int:
        page_end_int = page_int
    return page_int, page_end_int


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


def _page_size_from_layouts(
    layouts: dict[Any, Any] | None,
    payload: dict[str, Any],
) -> tuple[float | None, float | None]:
    if not layouts:
        return None, None
    layout = None
    page = payload.get("page_start") or payload.get("page")
    if page is not None:
        try:
            layout = layouts.get(int(page))
        except (TypeError, ValueError, AttributeError):
            layout = None
    if layout is None:
        layout = next(iter(layouts.values()), None)
    if layout is None:
        return None, None
    try:
        return float(layout.width), float(layout.height)
    except (TypeError, ValueError, AttributeError):
        return None, None


def _infer_content_type(
    row: dict[str, Any],
    *,
    chunk_text: str | None = None,
    layouts: dict[Any, Any] | None = None,
) -> str:
    image_count = 0
    span_count: int | None = None
    if layouts:
        page = row.get("page_start") or row.get("page")
        layout = None
        if page is not None:
            try:
                layout = layouts.get(int(page))
            except (TypeError, ValueError, AttributeError):
                layout = None
        if layout is None:
            layout = next(iter(layouts.values()), None)
        if layout is not None:
            image_count = int(getattr(layout, "image_count", 0) or 0)
            span_count = len(getattr(layout, "spans", []) or [])
    return infer_content_type(
        chunk_text or row.get("snippet") or "",
        highlight_available=bool(row.get("highlight_available")),
        layout_source=str(row.get("source") or SOURCE_NONE),
        text_engine=str(row.get("text_engine") or ""),
        image_count=image_count,
        span_count=span_count,
    )


def _with_visual_policy(
    payload: dict[str, Any],
    layouts: dict[Any, Any] | None = None,
) -> dict[str, Any]:
    width, height = _page_size_from_layouts(layouts, payload)
    return apply_visual_highlight_policy(
        payload,
        page_width=width,
        page_height=height,
    )


def _payload_from_cache(
    row: dict[str, Any],
    cleaned: str,
    cached: dict[str, Any],
) -> dict[str, Any]:
    payload = public_chunk_evidence(row)
    payload["quote"] = cleaned
    payload["quote_highlight_available"] = bool(cached.get("quote_highlight_available"))
    payload["quote_regions"] = _public_regions(cached.get("regions"))
    payload["quote_mapping_status"] = str(cached.get("match_type") or "failed")
    if cached.get("page_start") is not None:
        payload["page_start"] = int(cached["page_start"])
    if cached.get("page_end") is not None:
        payload["page_end"] = int(cached["page_end"])
    return _with_visual_policy(payload)


def _cache_quote_result(
    *,
    chunk_id: str,
    document_id: str,
    cleaned: str,
    mapped_ok: bool,
    status: str,
    quote_regions: list[dict[str, Any]],
    page_start: int | None = None,
    page_end: int | None = None,
) -> None:
    try:
        upsert_quote_region_cache(
            chunk_id=chunk_id,
            document_id=document_id,
            quote_text=cleaned,
            match_type=status,
            quote_highlight_available=mapped_ok,
            regions=quote_regions if mapped_ok else [],
            page_start=page_start,
            page_end=page_end,
        )
    except Exception:
        pass


def _load_page_layouts(
    document_id: str,
    pdf_path: str | None,
    pages: set[int],
) -> dict[int, Any]:
    path = pdf_path or document_pdf_path(document_id)
    if not path or not pages:
        return {}
    try:
        return extract_page_layouts(path, page_numbers=pages)
    except Exception:
        return {}


def public_chunk_evidence(row: dict[str, Any]) -> dict[str, Any]:
    payload = {
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
        "quote_mapping_status": row.get("quote_mapping_status") or "none",
        "content_type": _infer_content_type(row),
        "source": str(row.get("source") or SOURCE_NONE),
        "text_engine": str(row.get("text_engine") or ""),
    }
    return _with_visual_policy(payload)


def _fallback_chunk_evidence(
    *,
    document_id: str,
    chunk_id: str,
    chunk_text: str,
    meta: dict[str, Any],
    quote: str | None = None,
) -> dict[str, Any]:
    """Graceful payload when SQLite sidecar data is missing (legacy uploads)."""
    page_start, page_end = _page_bounds(meta)
    payload = {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "page_start": page_start,
        "page_end": page_end,
        "snippet": make_snippet(chunk_text),
        "highlight_available": False,
        "regions": [],
        "quote": quote,
        "quote_highlight_available": False,
        "quote_regions": [],
        "quote_mapping_status": "no_evidence_data",
        "content_type": infer_content_type(
            chunk_text,
            highlight_available=False,
            layout_source=SOURCE_NONE,
            text_engine="",
        ),
    }
    if quote and not compact_contains(chunk_text, quote):
        payload["quote_mapping_status"] = "not_in_chunk"
    return _with_visual_policy(payload)


def resolve_quote_evidence(
    *,
    document_id: str,
    chunk_id: str,
    quote: str | None,
    pdf_path: str | None,
) -> dict[str, Any] | None:
    row = get_chunk_evidence(chunk_id)

    if row and row.get("document_id") != document_id:
        return None

    if not row:
        chunk_text = _chunk_text_from_chroma(chunk_id)
        meta = _chunk_meta_from_chroma(chunk_id)
        if not chunk_text:
            return None
        if str(meta.get("document_id") or "") not in {"", document_id}:
            return None
        raw_quote = (quote or "").strip()
        cleaned = sanitize_quote(raw_quote) if raw_quote else None
        if raw_quote and not cleaned:
            payload = _fallback_chunk_evidence(
                document_id=document_id,
                chunk_id=chunk_id,
                chunk_text=chunk_text,
                meta=meta,
                quote=None,
            )
            payload["quote_mapping_status"] = "rejected"
            return payload
        return _fallback_chunk_evidence(
            document_id=document_id,
            chunk_id=chunk_id,
            chunk_text=chunk_text,
            meta=meta,
            quote=cleaned,
        )

    payload = public_chunk_evidence(row)
    raw_quote = (quote or "").strip()
    cleaned = sanitize_quote(raw_quote) if raw_quote else None
    payload["quote"] = cleaned
    if raw_quote and not cleaned:
        payload["quote_mapping_status"] = "rejected"
        return _with_visual_policy(payload)
    if not cleaned:
        return payload

    cached = get_quote_region_cache(chunk_id, cleaned)
    if cached is not None:
        return _payload_from_cache(row, cleaned, cached)

    chunk_text = _chunk_text_from_chroma(chunk_id) or ""
    pages = set(range(int(row["page_start"]), int(row["page_end"]) + 1))
    for item in row.get("ranges") or []:
        if isinstance(item, dict) and item.get("page") is not None:
            try:
                pages.add(int(item["page"]))
            except (TypeError, ValueError):
                continue

    layouts = _load_page_layouts(document_id, pdf_path, pages)
    payload["content_type"] = _infer_content_type(
        row, chunk_text=chunk_text, layouts=layouts
    )

    mapped = map_quote_to_regions(
        cleaned,
        chunk_text=chunk_text,
        layouts=layouts,
        page_start=int(row["page_start"]),
        page_end=int(row["page_end"]),
        ranges=row.get("ranges") or [],
        segments=row.get("segments") or [],
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

    payload = _with_visual_policy(payload, layouts)
    mapped_ok = bool(payload.get("quote_highlight_available") and payload.get("quote_regions"))

    _cache_quote_result(
        chunk_id=chunk_id,
        document_id=document_id,
        cleaned=cleaned,
        mapped_ok=mapped_ok,
        status=payload["quote_mapping_status"],
        quote_regions=payload["quote_regions"],
        page_start=payload.get("page_start"),
        page_end=payload.get("page_end"),
    )
    return payload


def _payload_from_localization(
    row: dict[str, Any],
    localized,
    *,
    cleaned_quote: str | None,
) -> dict[str, Any]:
    payload = public_chunk_evidence(row)
    payload["quote"] = localized.quote or cleaned_quote
    payload["quote_highlight_available"] = bool(localized.quote_highlight_available)
    payload["quote_regions"] = _public_regions(localized.quote_regions)
    payload["quote_mapping_status"] = localized.localization_status
    payload["localization_confidence"] = localized.localization_confidence
    payload["source_spans"] = list(localized.source_spans or [])
    if localized.page_start is not None:
        payload["page_start"] = localized.page_start
        payload["page"] = localized.page_start
    if localized.page_end is not None:
        payload["page_end"] = localized.page_end
    return _with_visual_policy(payload)


def _int_page(value: Any) -> int | None:
    try:
        page = int(value)
    except (TypeError, ValueError):
        return None
    return page if page >= 1 else None


def _window_from_record(
    chunk_id: str,
    document_id: str,
    text: str,
    meta: dict[str, Any],
    row: dict[str, Any] | None = None,
) -> ReanchorWindow:
    row = row or {}
    page_start = _int_page(
        row.get("page_start") or meta.get("page_start") or meta.get("page_number")
    )
    page_end = _int_page(row.get("page_end") or meta.get("page_end") or page_start)
    page_number = _int_page(meta.get("page_number") or page_start)
    return ReanchorWindow(
        chunk_id=chunk_id,
        document_id=document_id,
        text=text or "",
        page_start=page_start,
        page_end=page_end,
        page_number=page_number,
    )


def _load_neighbor_windows(
    document_id: str,
    primary: ReanchorWindow,
    meta: dict[str, Any],
    *,
    radius: int,
) -> list[ReanchorWindow]:
    ids = neighbor_chunk_ids(meta, radius=max(0, min(int(radius), 1)))
    if not ids:
        return [primary]
    try:
        from rag import get_collection

        payload = get_collection().get(ids=ids, include=["documents", "metadatas"])
    except Exception:
        return [primary]

    got_ids = list(payload.get("ids") or [])
    documents = list(payload.get("documents") or [])
    metadatas = list(payload.get("metadatas") or [])
    by_id: dict[str, ReanchorWindow] = {}
    for idx, nid in enumerate(got_ids):
        text = documents[idx] if idx < len(documents) else ""
        if not isinstance(text, str) or not text.strip():
            continue
        nmeta = metadatas[idx] if idx < len(metadatas) and isinstance(metadatas[idx], dict) else {}
        if str(nmeta.get("document_id") or document_id) != document_id:
            continue
        nrow = get_chunk_evidence(str(nid))
        if nrow and str(nrow.get("document_id") or "") not in {"", document_id}:
            continue
        by_id[str(nid)] = _window_from_record(str(nid), document_id, text, nmeta, nrow)

    ordered: list[ReanchorWindow] = []
    prev_id = str(meta.get("prev_chunk_id") or "")
    next_id = str(meta.get("next_chunk_id") or "")
    if prev_id and prev_id in by_id:
        ordered.append(by_id[prev_id])
    ordered.append(primary)
    if next_id and next_id in by_id:
        ordered.append(by_id[next_id])
    return ordered or [primary]


def _pages_for_windows(
    windows: list[ReanchorWindow],
    row: dict[str, Any] | None,
) -> set[int]:
    pages: set[int] = set()
    for window in windows:
        start = window.page_start or window.page_number
        end = window.page_end or start
        if isinstance(start, int) and isinstance(end, int) and start >= 1:
            pages.update(range(start, max(end, start) + 1))
    for item in (row or {}).get("ranges") or []:
        if not isinstance(item, dict) or item.get("page") is None:
            continue
        page = _int_page(item.get("page"))
        if page:
            pages.add(page)
    return pages


def resolve_claim_evidence(
    *,
    document_id: str,
    chunk_id: str,
    claim_text: str,
    quote: str | None = None,
    pdf_path: str | None = None,
) -> dict[str, Any] | None:
    """
    Claim-aware evidence localization with ±1 neighbor re-anchoring.
    """
    row = get_chunk_evidence(chunk_id)
    if row and row.get("document_id") != document_id:
        return None

    if not row:
        return resolve_quote_evidence(
            document_id=document_id,
            chunk_id=chunk_id,
            quote=quote,
            pdf_path=pdf_path,
        )

    cleaned_quote = sanitize_quote(quote) if quote else None
    chunk_text = _chunk_text_from_chroma(chunk_id) or ""
    meta = _chunk_meta_from_chroma(chunk_id)
    primary = _window_from_record(chunk_id, document_id, chunk_text, meta, row)
    windows = _load_neighbor_windows(
        document_id,
        primary,
        meta,
        radius=REANCHOR_NEIGHBOR_RADIUS,
    )
    multi = len(windows) > 1

    cache_text = localization_cache_key(claim_text=claim_text, quote=cleaned_quote)
    if cache_text and not multi:
        cached = get_quote_region_cache(chunk_id, cache_text)
        if cached is not None:
            payload = public_chunk_evidence(row)
            payload["quote"] = cleaned_quote or cache_text
            payload["quote_highlight_available"] = bool(cached.get("quote_highlight_available"))
            payload["quote_regions"] = _public_regions(cached.get("regions"))
            payload["quote_mapping_status"] = str(cached.get("match_type") or STATUS_UNRESOLVED)
            if cached.get("page_start") is not None:
                payload["page_start"] = int(cached["page_start"])
                payload["page"] = int(cached["page_start"])
            if cached.get("page_end") is not None:
                payload["page_end"] = int(cached["page_end"])
            return _with_visual_policy(payload)

    pages = _pages_for_windows(windows, row)
    layouts: dict[Any, Any] = _load_page_layouts(document_id, pdf_path, pages)

    result = reanchor_claim(
        claim_text,
        cleaned_quote,
        windows,
        primary_chunk_id=chunk_id,
        layouts=layouts,
        ranges=None if multi else (row.get("ranges") or []),
        segments=None if multi else (row.get("segments") or []),
        highlight_available=bool(row.get("highlight_available")),
    )

    owner_row = row
    if result.chunk_id != chunk_id:
        neighbor_row = get_chunk_evidence(result.chunk_id)
        if neighbor_row and str(neighbor_row.get("document_id") or document_id) == document_id:
            owner_row = neighbor_row

    payload = _payload_from_localization(
        owner_row,
        result.localization,
        cleaned_quote=cleaned_quote,
    )
    payload["chunk_id"] = result.chunk_id
    payload["content_type"] = _infer_content_type(
        owner_row,
        chunk_text=_chunk_text_from_chroma(result.chunk_id) or chunk_text,
        layouts=layouts,
    )
    if result.page is not None:
        payload["page_start"] = result.page
        payload["page"] = result.page
    if result.cross_chunk:
        payload["reanchor_from_chunk_id"] = chunk_id
    payload["reanchor_cross_chunk"] = result.cross_chunk
    payload["reanchor_cross_page"] = result.cross_page
    if result.source_spans and not payload.get("source_spans"):
        payload["source_spans"] = list(result.source_spans)

    payload = _with_visual_policy(payload, layouts)
    mapped_ok = bool(payload.get("quote_highlight_available") and payload.get("quote_regions"))

    if cache_text:
        _cache_quote_result(
            chunk_id=result.chunk_id,
            document_id=document_id,
            cleaned=cache_text,
            mapped_ok=mapped_ok,
            status=str(payload.get("quote_mapping_status") or STATUS_UNRESOLVED),
            quote_regions=payload["quote_regions"],
            page_start=payload.get("page_start"),
            page_end=payload.get("page_end"),
        )
    return payload
