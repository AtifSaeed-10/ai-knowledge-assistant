"""
Cross-chunk / cross-page evidence re-anchoring.

After a claim is bound to a retrieval chunk, look at the immediate previous and
next chunks in the same document, stitch overlapping text, and map the minimum
supporting span onto PDF regions. The citation page follows the highlight, not
the retrieval slot's page_number.

Neighbor walk is bounded (±1). No document-specific rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from claim_localizer import LocalizationResult, claim_token_coverage, localize_claim_in_chunk
from evidence_mapping import compact_contains

_MIN_OVERLAP = 24
_MAX_OVERLAP = 800


@dataclass
class ReanchorWindow:
    chunk_id: str
    document_id: str = ""
    text: str = ""
    page_start: int | None = None
    page_end: int | None = None
    page_number: int | None = None


@dataclass
class ReanchorResult:
    chunk_id: str
    localization: LocalizationResult
    stitched: bool = False
    neighbor_ids: list[str] = field(default_factory=list)
    page: int | None = None
    cross_chunk: bool = False
    cross_page: bool = False
    source_spans: list[str] = field(default_factory=list)


def join_overlapping(left: str, right: str) -> str:
    """Join two chunk texts, dropping the duplicated overlap tail/head."""
    if not left:
        return right or ""
    if not right:
        return left
    if right in left:
        return left
    if left in right:
        return right
    max_k = min(len(left), len(right), _MAX_OVERLAP)
    for size in range(max_k, _MIN_OVERLAP - 1, -1):
        if left.endswith(right[:size]):
            return left + right[size:]
    left_s = left.rstrip()
    right_s = right.lstrip()
    max_k = min(len(left_s), len(right_s), _MAX_OVERLAP)
    for size in range(max_k, _MIN_OVERLAP - 1, -1):
        if left_s.endswith(right_s[:size]):
            return left_s + right_s[size:]
    return left_s + " " + right_s


def stitch_windows(
    windows: list[ReanchorWindow],
) -> tuple[str, list[tuple[str, int, int]]]:
    """
    Concatenate windows in order.

    Returns stitched text and (chunk_id, start, end) ranges for the unique
    suffix contributed by each window (overlap stays with the earlier chunk).
    """
    stitched = ""
    spans: list[tuple[str, int, int]] = []
    for window in windows:
        text = window.text or ""
        if not text:
            continue
        if not stitched:
            spans.append((window.chunk_id, 0, len(text)))
            stitched = text
            continue
        before = len(stitched)
        joined = join_overlapping(stitched, text)
        start = before
        stitched = joined
        end = len(stitched)
        if end > start:
            spans.append((window.chunk_id, start, end))
        else:
            spans.append((window.chunk_id, max(0, end - 1), end))
    return stitched, spans


def _span_offsets(haystack: str, needle: str) -> tuple[int, int] | None:
    if not haystack or not needle:
        return None
    at = haystack.find(needle)
    if at >= 0:
        return at, at + len(needle)
    lower_hay = haystack.lower()
    lower_needle = needle.lower()
    at = lower_hay.find(lower_needle)
    if at >= 0:
        return at, at + len(needle)
    return None


def owner_chunk_id(
    span_start: int,
    span_end: int,
    spans: list[tuple[str, int, int]],
    fallback: str,
) -> str:
    if not spans:
        return fallback
    best_id = fallback or spans[0][0]
    best_overlap = -1
    for chunk_id, start, end in spans:
        overlap = max(0, min(span_end, end) - max(span_start, start))
        if overlap > best_overlap:
            best_overlap = overlap
            best_id = chunk_id
    return best_id


def owner_chunk_for_span_text(
    span_text: str,
    loc_text: str,
    windows: list[ReanchorWindow],
    offset_map: list[tuple[str, int, int]],
    fallback: str,
) -> str:
    offsets = _span_offsets(loc_text, span_text)
    scored: list[tuple[float, str]] = []
    for window in windows:
        text = window.text or ""
        if not text:
            continue
        if compact_contains(text, span_text):
            scored.append((1.0, window.chunk_id))
        else:
            scored.append((claim_token_coverage(span_text, text), window.chunk_id))
    scored.sort(key=lambda item: -item[0])
    if scored and scored[0][0] >= 0.45:
        if len(scored) == 1 or scored[0][0] >= scored[1][0] + 0.08:
            return scored[0][1]
    if offsets:
        return owner_chunk_id(offsets[0], offsets[1], offset_map, fallback)
    return scored[0][1] if scored else fallback


def _page_bounds(windows: list[ReanchorWindow]) -> tuple[int, int]:
    starts: list[int] = []
    ends: list[int] = []
    for window in windows:
        if isinstance(window.page_start, int) and window.page_start >= 1:
            starts.append(window.page_start)
        elif isinstance(window.page_number, int) and window.page_number >= 1:
            starts.append(window.page_number)
        if isinstance(window.page_end, int) and window.page_end >= 1:
            ends.append(window.page_end)
        elif isinstance(window.page_number, int) and window.page_number >= 1:
            ends.append(window.page_number)
    if not starts:
        return 1, 1
    page_start = min(starts)
    page_end = max(ends) if ends else page_start
    if page_end < page_start:
        page_end = page_start
    return page_start, page_end


def _display_page(
    localization: LocalizationResult,
    owner: ReanchorWindow | None,
    primary: ReanchorWindow,
) -> int | None:
    if isinstance(localization.page_start, int) and localization.page_start >= 1:
        return localization.page_start
    for candidate in (owner, primary):
        if candidate is None:
            continue
        for value in (candidate.page_number, candidate.page_start):
            if isinstance(value, int) and value >= 1:
                return value
    return None


def _window_by_id(windows: list[ReanchorWindow], chunk_id: str) -> ReanchorWindow | None:
    for window in windows:
        if window.chunk_id == chunk_id:
            return window
    return None


def reanchor_claim(
    claim: str,
    quote: str | None,
    windows: list[ReanchorWindow],
    *,
    primary_chunk_id: str,
    layouts: dict[Any, Any] | None = None,
    ranges: list[dict[str, Any]] | None = None,
    segments: list[dict[str, Any]] | None = None,
    highlight_available: bool = False,
) -> ReanchorResult:
    """
    Localize a claim against a primary chunk plus optional neighbors.

    Uses stitched text when more than one window is present so a sentence split
    across a chunk boundary can still resolve to a minimum PDF span.
    """
    usable = [row for row in windows if row.chunk_id and (row.text or "").strip()]
    if not usable:
        empty = LocalizationResult()
        return ReanchorResult(
            chunk_id=primary_chunk_id,
            localization=empty,
            page=None,
        )

    primary = _window_by_id(usable, primary_chunk_id) or usable[0]
    stitched, offset_map = stitch_windows(usable)
    multi = len(usable) > 1
    page_start, page_end = _page_bounds(usable)

    # Multi-window: map against the stitch + union of page layouts.
    # Single-window: keep index-time ranges/segments for tighter boxes.
    loc_text = stitched if multi else (primary.text or stitched)
    loc_ranges = None if multi else ranges
    loc_segments = None if multi else segments

    localized = localize_claim_in_chunk(
        claim,
        loc_text,
        quote=quote,
        layouts=layouts or {},
        page_start=page_start,
        page_end=page_end,
        ranges=loc_ranges,
        segments=loc_segments,
        chunk_highlight_available=highlight_available,
    )

    owner_id = primary.chunk_id
    span_text = ""
    if localized.source_spans:
        span_text = localized.source_spans[0]
    elif localized.quote:
        span_text = localized.quote
    elif quote and compact_contains(loc_text, quote):
        span_text = quote

    if span_text:
        owner_id = owner_chunk_for_span_text(
            span_text,
            loc_text,
            usable,
            offset_map,
            primary.chunk_id,
        )

    owner = _window_by_id(usable, owner_id) or primary
    page = _display_page(localized, owner, primary)
    retrieval_page = primary.page_number if isinstance(primary.page_number, int) else primary.page_start
    neighbor_ids = [row.chunk_id for row in usable if row.chunk_id != primary.chunk_id]

    return ReanchorResult(
        chunk_id=owner_id,
        localization=localized,
        stitched=multi,
        neighbor_ids=neighbor_ids,
        page=page,
        cross_chunk=owner_id != primary.chunk_id,
        cross_page=bool(
            isinstance(page, int)
            and isinstance(retrieval_page, int)
            and page != retrieval_page
        ),
        source_spans=list(localized.source_spans or []),
    )


def neighbor_chunk_ids(meta: dict[str, Any] | None, *, radius: int = 1) -> list[str]:
    """Return prev/next ids from Chroma metadata. Radius is capped at 1."""
    if not meta or radius <= 0:
        return []
    ids: list[str] = []
    prev_id = str(meta.get("prev_chunk_id") or "").strip()
    next_id = str(meta.get("next_chunk_id") or "").strip()
    if prev_id:
        ids.append(prev_id)
    if next_id:
        ids.append(next_id)
    return ids
