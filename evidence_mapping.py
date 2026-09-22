"""
Index-time evidence provenance: chunk text → page slices → PDF span bboxes.

Alignment is the mapping-proof algorithm:
1. Exact substring of concatenated dict spans
2. Whitespace-normalized compact(plain) == compact(spans) index map
3. Compact substring search
4. Hyphen-stripped compact search

Chunking and extraction are not modified. PAGE_JOIN-merged chunks that are
not a substring of concatenated page text are recovered by mapping each
join-separated part independently.

Coordinates are PyMuPDF page space (origin top-left, PDF points). Never invent
boxes: highlight_available is true only when every non-empty slice mapped to
at least one real span bbox.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import pymupdf as fitz

from chunking import PAGE_JOIN, build_document_text
from page_ocr import OCR_ENGINE
from pdf_extraction import PRIMARY_ENGINE

logger = logging.getLogger(__name__)

SOURCE_NATIVE = "native"
SOURCE_NONE = "none"
COORD_SPACE_PDF = "pdf"
SNIPPET_MAX = 280

SUCCESS_MATCH_TYPES = frozenset(
    {"exact", "normalized", "fuzzy_compact", "hyphen_fuzzy"}
)


@dataclass
class Span:
    text: str
    bbox: tuple[float, float, float, float]
    line_bbox: tuple[float, float, float, float]


@dataclass
class PageLayout:
    page_number: int
    width: float
    height: float
    plain: str
    spans: list[Span]
    source: str
    engine: str
    image_count: int = 0


# PDF text often uses these instead of ASCII. Mapping keeps compact indices
# aligned to the original string (ligatures expand to two compact chars).
_PDF_CHAR_MAP = {
    "\u00a0": " ",  # nbsp
    "\u202f": " ",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\ufb01": "fi",
    "\ufb02": "fl",
}


def compact(text: str, drop_hyphens: bool = False) -> tuple[str, list[int]]:
    """Drop whitespace (and optionally hyphens); map compact index → original."""
    chars: list[str] = []
    orig: list[int] = []
    for index, char in enumerate(text):
        if char == "\u00ad":  # soft hyphen
            continue
        mapped = _PDF_CHAR_MAP.get(char, char)
        for piece in mapped:
            if piece.isspace():
                continue
            if drop_hyphens and piece == "-":
                continue
            chars.append(piece)
            orig.append(index)
    return "".join(chars), orig


def concat_spans(spans: list[Span]) -> tuple[str, list[int]]:
    parts: list[str] = []
    char_to_span: list[int] = []
    for index, span in enumerate(spans):
        parts.append(span.text)
        char_to_span.extend([index] * len(span.text))
    return "".join(parts), char_to_span


def unique_boxes(
    boxes: list[tuple[float, float, float, float]],
) -> list[list[float]]:
    seen: set[tuple[float, float, float, float]] = set()
    out: list[list[float]] = []
    for box in boxes:
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        key = (
            round(box[0], 3),
            round(box[1], 3),
            round(box[2], 3),
            round(box[3], 3),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append([round(value, 2) for value in box])
    return out


def make_snippet(text: str, limit: int = SNIPPET_MAX) -> str:
    collapsed = re.sub(r"\s+", " ", (text or "").strip())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1].rstrip() + "…"


def extract_spans(page: fitz.Page) -> list[Span]:
    payload = page.get_text("dict") or {}
    spans: list[Span] = []
    for block in payload.get("blocks") or []:
        if block.get("type") != 0:
            continue
        for line in block.get("lines") or []:
            line_bbox = tuple(line.get("bbox") or (0.0, 0.0, 0.0, 0.0))
            for item in line.get("spans") or []:
                box = tuple(item.get("bbox") or (0.0, 0.0, 0.0, 0.0))
                spans.append(
                    Span(
                        text=item.get("text") or "",
                        bbox=(
                            float(box[0]),
                            float(box[1]),
                            float(box[2]),
                            float(box[3]),
                        ),
                        line_bbox=(
                            float(line_bbox[0]),
                            float(line_bbox[1]),
                            float(line_bbox[2]),
                            float(line_bbox[3]),
                        ),
                    )
                )
    return spans


def extract_page_layouts(
    pdf_path: str,
    page_numbers: set[int] | None = None,
) -> dict[int, PageLayout]:
    """Read page plain text and dict spans. Keyed by 1-based page number."""
    wanted = {int(page) for page in page_numbers} if page_numbers else None
    layouts: dict[int, PageLayout] = {}
    document = fitz.open(pdf_path)
    try:
        for index in range(document.page_count):
            page_number = index + 1
            if wanted is not None and page_number not in wanted:
                continue
            page = document.load_page(index)
            spans = extract_spans(page)
            plain = page.get_text("text") or ""
            if not plain.strip():
                plain = "".join(span.text for span in spans)
            try:
                image_count = len(page.get_images(full=True) or [])
            except Exception:
                image_count = 0
            layouts[page_number] = PageLayout(
                page_number=page_number,
                width=float(page.rect.width),
                height=float(page.rect.height),
                plain=plain,
                spans=spans,
                source=SOURCE_NATIVE if spans else SOURCE_NONE,
                engine=PRIMARY_ENGINE,
                image_count=image_count,
            )
    finally:
        document.close()
    return layouts


def split_range_by_pages(
    start: int,
    end: int,
    page_spans: list[tuple[int, int, int]],
    full_text: str,
) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for page_start, page_end, page_number in page_spans:
        left = max(start, page_start)
        right = min(end, page_end)
        if left < right:
            parts.append(
                {
                    "page": page_number,
                    "start": left,
                    "end": right,
                    "text": full_text[left:right],
                    "page_char_start": left - page_start,
                    "page_char_end": right - page_start,
                }
            )
    return parts


def locate_chunk_slices(
    chunk_text: str,
    full_text: str,
    page_spans: list[tuple[int, int, int]],
    search_from: int,
) -> tuple[list[dict[str, Any]], int, bool, bool]:
    """
    Locate a chunk in concatenated page text.

    Returns (slices, next_search_from, join_recovered, fully_located).
    join_recovered is True when the chunk was not a contiguous substring and
    PAGE_JOIN-separated parts were mapped instead (merge_tiny_chunks).
    """
    located = full_text.find(chunk_text, search_from)
    if located == -1:
        located = full_text.find(chunk_text)
    if located != -1:
        slices = split_range_by_pages(
            located,
            located + len(chunk_text),
            page_spans,
            full_text,
        )
        return slices, max(search_from, located + 1), False, True

    slices: list[dict[str, Any]] = []
    cursor = search_from
    expected = [part for part in chunk_text.split(PAGE_JOIN) if part]
    found = 0
    for part in expected:
        index = full_text.find(part, cursor)
        if index == -1:
            index = full_text.find(part)
        if index == -1:
            continue
        found += 1
        slices.extend(
            split_range_by_pages(
                index,
                index + len(part),
                page_spans,
                full_text,
            )
        )
        cursor = max(cursor, index + 1)

    fully_located = found == len(expected) and bool(expected)
    next_from = cursor if slices else search_from
    return slices, next_from, True, fully_located


def map_slice_to_spans(slice_text: str, spans: list[Span], plain: str) -> dict[str, Any]:
    """Map one page-local chunk slice onto dict spans (mapping-proof order)."""
    failed = {
        "match_type": "failed",
        "confidence": 0.0,
        "matched_span_text": "",
        "bbox_count": 0,
        "regions": [],
        "notes": "",
    }
    if not slice_text.strip():
        return {
            "match_type": "empty_slice",
            "confidence": 1.0,
            "matched_span_text": "",
            "bbox_count": 0,
            "regions": [],
            "notes": "whitespace-only page slice",
        }
    if not spans:
        failed["notes"] = "no dict spans on page"
        return failed

    span_concat, char_to_span = concat_spans(spans)
    span_c, span_orig = compact(span_concat)
    needle_c, _ = compact(slice_text)
    plain_c, _ = compact(plain)
    page_compact_eq = plain_c == span_c

    def spans_for_compact_range(hay_orig: list[int], start: int, end: int) -> dict[str, Any]:
        span_ids: list[int] = []
        for compact_i in range(start, end):
            orig_i = hay_orig[compact_i]
            span_ids.append(char_to_span[orig_i])
        ordered: list[int] = []
        seen_ids: set[int] = set()
        for span_id in span_ids:
            if span_id not in seen_ids:
                seen_ids.add(span_id)
                ordered.append(span_id)
        boxes = unique_boxes([spans[i].bbox for i in ordered])
        matched_text = "".join(spans[i].text for i in ordered)
        return {
            "matched_span_text": matched_text,
            "bbox_count": len(boxes),
            "regions": boxes,
            "span_count": len(ordered),
        }

    exact_at = span_concat.find(slice_text)
    if exact_at != -1 and needle_c:
        start_c = len(compact(span_concat[:exact_at])[0])
        end_c = start_c + len(needle_c)
        mapped = spans_for_compact_range(span_orig, start_c, end_c)
        mapped.update(
            {
                "match_type": "exact",
                "confidence": 1.0,
                "notes": "exact substring of span concat",
            }
        )
        return mapped

    if needle_c and page_compact_eq:
        plain_at = plain.find(slice_text)
        if plain_at != -1:
            start_c = len(compact(plain[:plain_at])[0])
            end_c = start_c + len(needle_c)
            if span_c[start_c:end_c] == needle_c:
                mapped = spans_for_compact_range(span_orig, start_c, end_c)
                mapped.update(
                    {
                        "match_type": "normalized",
                        "confidence": 0.9,
                        "notes": "whitespace-normalized; page compact identity",
                    }
                )
                return mapped

    if needle_c:
        hits: list[int] = []
        start = 0
        while True:
            at = span_c.find(needle_c, start)
            if at == -1:
                break
            hits.append(at)
            start = at + 1
            if len(hits) > 20:
                break
        if hits:
            chosen = hits[0]
            plain_at = plain.find(slice_text)
            if plain_at != -1 and plain_c:
                target = len(compact(plain[:plain_at])[0])
                chosen = min(hits, key=lambda hit: abs(hit - target))
            mapped = spans_for_compact_range(
                span_orig, chosen, chosen + len(needle_c)
            )
            mapped.update(
                {
                    "match_type": "fuzzy_compact",
                    "confidence": 0.85 if page_compact_eq else 0.7,
                    "notes": (
                        f"compact substring; hits={len(hits)} "
                        f"page_compact_eq={page_compact_eq}"
                    ),
                }
            )
            return mapped

    needle_h, _ = compact(slice_text, drop_hyphens=True)
    span_h, span_h_orig = compact(span_concat, drop_hyphens=True)
    if needle_h:
        at = span_h.find(needle_h)
        if at != -1:
            span_ids: list[int] = []
            for compact_i in range(at, at + len(needle_h)):
                orig_i = span_h_orig[compact_i]
                span_ids.append(char_to_span[orig_i])
            ordered = list(dict.fromkeys(span_ids))
            boxes = unique_boxes([spans[i].bbox for i in ordered])
            return {
                "match_type": "hyphen_fuzzy",
                "confidence": 0.6,
                "matched_span_text": "".join(spans[i].text for i in ordered),
                "bbox_count": len(boxes),
                "regions": boxes,
                "notes": "matched after dropping hyphens and whitespace",
            }

    failed["notes"] = (
        f"no compact match; page_compact_eq={page_compact_eq} "
        f"plain_c={len(plain_c)} span_c={len(span_c)} needle_c={len(needle_c)}"
    )
    return failed


def _regions_for_page(page_number: int, boxes: list[list[float]]) -> list[dict[str, Any]]:
    return [
        {
            "page": page_number,
            "x0": box[0],
            "y0": box[1],
            "x1": box[2],
            "y1": box[3],
            "coord_space": COORD_SPACE_PDF,
        }
        for box in boxes
    ]


def compact_contains(haystack: str, needle: str) -> bool:
    hay_c, _ = compact(haystack or "")
    needle_c, _ = compact(needle or "")
    if needle_c and needle_c in hay_c:
        return True
    # Line-end hyphenation: "exam-\nples" vs "examples"
    hay_h, _ = compact(haystack or "", drop_hyphens=True)
    needle_h, _ = compact(needle or "", drop_hyphens=True)
    return bool(needle_h) and needle_h in hay_h


def _empty_quote_map(match_type: str = "failed") -> dict[str, Any]:
    return {
        "quote_highlight_available": False,
        "regions": [],
        "match_type": match_type,
        "pages": [],
    }


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_CLAUSE_SPLIT_RE = re.compile(r"\s*;\s+|\s+—\s+|\s+-\s+")


def spans_for_index_segments(text: str, *, min_chars: int = 12) -> list[dict[str, Any]]:
    """Sentence spans, with long sentences further split into clause-sized units."""
    parts: list[dict[str, Any]] = []
    for sentence_part in split_sentences(text, min_chars=min_chars):
        sentence = sentence_part["text"]
        base_start = int(sentence_part["char_start"])
        if len(sentence) <= 100:
            parts.append(dict(sentence_part))
            continue
        subparts: list[dict[str, Any]] = []
        cursor = 0
        for match in _CLAUSE_SPLIT_RE.finditer(sentence):
            end = match.start()
            clause = sentence[cursor:end].strip()
            if len(clause) >= min_chars:
                subparts.append(
                    {
                        "text": clause,
                        "char_start": base_start + cursor,
                        "char_end": base_start + end,
                    }
                )
            cursor = match.end()
        tail = sentence[cursor:].strip()
        if len(tail) >= min_chars:
            subparts.append(
                {
                    "text": tail,
                    "char_start": base_start + cursor,
                    "char_end": base_start + len(sentence),
                }
            )
        if subparts:
            parts.extend(subparts)
        else:
            parts.append(dict(sentence_part))
    for index, item in enumerate(parts):
        item["index"] = index
    return parts


_FIGURE_LABEL_RE = re.compile(
    r"\b(?:figure|fig\.?|illustration|plate|diagram)\s*\.?\s*\d",
    re.IGNORECASE,
)
_FIGURE_LEAD_RE = re.compile(
    r"^(?:figure|fig\.?|illustration|plate|diagram)\b",
    re.IGNORECASE,
)
_TABLE_LABEL_RE = re.compile(
    r"\b(?:table|tbl\.?)\s*\.?\s*\d",
    re.IGNORECASE,
)


def infer_content_type(
    chunk_text: str,
    *,
    highlight_available: bool,
    layout_source: str,
    text_engine: str | None = None,
    image_count: int = 0,
    span_count: int | None = None,
) -> str:
    """Classify evidence for UI and orchestrator (not all PDF content is highlightable)."""
    text = (chunk_text or "").strip()
    if not highlight_available and layout_source == SOURCE_NONE:
        if text_engine and "ocr" in str(text_engine).lower():
            return "scanned_ocr"
        return "scanned_or_image"
    # Image-heavy page with almost no native text — still a scan, not a figure.
    if (
        not highlight_available
        and image_count >= 1
        and span_count is not None
        and span_count < 8
        and len(text) < 80
    ):
        return "scanned_or_image"
    if _FIGURE_LABEL_RE.search(text) and len(text) < 280:
        return "figure_caption"
    if _FIGURE_LEAD_RE.search(text) and len(text) < 180:
        return "figure_caption"
    if _TABLE_LABEL_RE.search(text) and len(text) < 400:
        return "table"
    if text.count("|") >= 3 or text.count("\t") >= 2:
        return "table"
    if not highlight_available:
        return "low_text_layout"
    return "native_text"

def split_sentences(text: str, *, min_chars: int = 12) -> list[dict[str, Any]]:
    """Split chunk text into sentence spans for index-time segment mapping."""
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    parts: list[dict[str, Any]] = []
    cursor = 0
    for match in _SENTENCE_SPLIT_RE.finditer(cleaned):
        end = match.start()
        sentence = cleaned[cursor:end].strip()
        if len(sentence) >= min_chars:
            parts.append(
                {
                    "text": sentence,
                    "char_start": cursor,
                    "char_end": end,
                }
            )
        cursor = match.end()
    tail = cleaned[cursor:].strip()
    if len(tail) >= min_chars:
        parts.append(
            {
                "text": tail,
                "char_start": cursor,
                "char_end": len(cleaned),
            }
        )
    if not parts and len(cleaned) >= min_chars:
        parts.append({"text": cleaned, "char_start": 0, "char_end": len(cleaned)})
    for index, item in enumerate(parts):
        item["index"] = index
    return parts


def build_sentence_segments(
    chunk_text: str,
    *,
    layouts: dict[int, PageLayout],
    page_start: int,
    page_end: int,
    ranges: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Pre-map sentences at index time for tighter quote highlights."""
    segments: list[dict[str, Any]] = []
    for part in spans_for_index_segments(chunk_text):
        sentence = part["text"]
        mapped = map_quote_to_regions(
            sentence,
            chunk_text=chunk_text,
            layouts=layouts,
            page_start=page_start,
            page_end=page_end,
            ranges=ranges,
        )
        highlight = bool(mapped.get("quote_highlight_available"))
        regions = mapped.get("regions") or []
        segments.append(
            {
                "index": part["index"],
                "text": sentence,
                "char_start": part["char_start"],
                "char_end": part["char_end"],
                "match_type": mapped.get("match_type") or "failed",
                "highlight_available": highlight,
                "regions": regions if highlight else [],
                "pages": mapped.get("pages") or [],
            }
        )
    return segments


def _find_matching_segments(
    quote: str,
    segments: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Return pre-indexed segments that contain the quote (compact match)."""
    if not segments:
        return []
    quote_c, _ = compact(quote)
    if not quote_c:
        return []
    matches: list[dict[str, Any]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        text = segment.get("text") or ""
        seg_c, _ = compact(text)
        if not seg_c:
            continue
        if quote_c in seg_c or seg_c in quote_c:
            matches.append(segment)
    if matches:
        return matches
    # Prefer the shortest segment that still contains the quote words.
    for segment in segments:
        text = segment.get("text") or ""
        if compact_contains(text, quote):
            matches.append(segment)
    return matches


def _regions_from_segments(segments: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str, list[int]]:
    regions: list[dict[str, Any]] = []
    match_types: list[str] = []
    pages: set[int] = set()
    for segment in segments:
        if not segment.get("highlight_available"):
            continue
        for region in segment.get("regions") or []:
            if isinstance(region, dict):
                regions.append(region)
                page = region.get("page")
                if page is not None:
                    try:
                        pages.add(int(page))
                    except (TypeError, ValueError):
                        pass
        match_types.append(str(segment.get("match_type") or "failed"))
    if not regions:
        return [], "failed", []
    rank = {
        "failed": 0,
        "empty_slice": 1,
        "hyphen_fuzzy": 2,
        "fuzzy_compact": 3,
        "normalized": 4,
        "exact": 5,
    }
    overall = min(match_types, key=lambda item: rank.get(item, 0)) if match_types else "failed"
    return regions, overall, sorted(pages)


def _map_slices_to_regions(
    slices: list[dict[str, Any]],
    layouts: dict[int, PageLayout],
) -> tuple[list[dict[str, Any]], str]:
    regions: list[dict[str, Any]] = []
    match_types: list[str] = []
    nonempty_slices = 0
    nonempty_success = 0
    for slice_row in slices:
        page_number = int(slice_row["page"])
        layout = layouts.get(page_number)
        slice_text = slice_row.get("text") or ""
        if layout is None:
            match_types.append("failed")
            if slice_text.strip():
                nonempty_slices += 1
            continue
        mapped = map_slice_to_spans(
            slice_text, layout.spans, _layout_search_text(layout)
        )
        match_type = mapped["match_type"]
        match_types.append(match_type)
        page_regions = _regions_for_page(page_number, mapped.get("regions") or [])
        if slice_text.strip():
            nonempty_slices += 1
            if match_type in SUCCESS_MATCH_TYPES and page_regions:
                nonempty_success += 1
                regions.extend(page_regions)
    rank = {
        "failed": 0,
        "empty_slice": 1,
        "hyphen_fuzzy": 2,
        "fuzzy_compact": 3,
        "normalized": 4,
        "exact": 5,
    }
    overall = min(match_types, key=lambda item: rank.get(item, 0)) if match_types else "failed"
    if nonempty_slices == 0 or nonempty_success != nonempty_slices or not regions:
        return [], overall if overall in SUCCESS_MATCH_TYPES else "failed"
    return regions, overall


def _layout_search_text(layout: PageLayout) -> str:
    """Text used to locate a quote on a page. Prefer span text (source of boxes)."""
    span_text = "".join(span.text for span in (layout.spans or []))
    if span_text.strip():
        return span_text
    return layout.plain or ""


def _hyphen_compact_span(window: str, quote: str) -> tuple[int, int] | None:
    hay_h, hay_orig = compact(window, drop_hyphens=True)
    needle_h, _ = compact(quote, drop_hyphens=True)
    if not needle_h:
        return None
    at = hay_h.find(needle_h)
    if at == -1:
        return None
    return hay_orig[at], hay_orig[at + len(needle_h) - 1] + 1


def _region_area(regions: list[dict[str, Any]]) -> float:
    area = 0.0
    for item in regions:
        try:
            area += max(0.0, float(item["x1"]) - float(item["x0"])) * max(
                0.0, float(item["y1"]) - float(item["y0"])
            )
        except (KeyError, TypeError, ValueError):
            continue
    return area


def _map_quote_via_page_spans(
    quote: str,
    layouts: dict[int, PageLayout],
    page_start: int,
    page_end: int,
) -> dict[str, Any]:
    """
    Last resort: map the full quote onto each page's dict spans.

    Uses real span boxes only. Prefers the single page with the smallest
    matching area so a quote that lives on one page is not painted elsewhere.
    """
    hits: list[tuple[int, str, list[dict[str, Any]]]] = []
    for page_number in range(int(page_start), int(page_end) + 1):
        layout = layouts.get(page_number)
        if layout is None or not layout.spans:
            continue
        search = _layout_search_text(layout)
        if not compact_contains(search, quote):
            continue
        mapped = map_slice_to_spans(quote, layout.spans, search)
        page_regions = _regions_for_page(page_number, mapped.get("regions") or [])
        match_type = str(mapped.get("match_type") or "failed")
        if match_type in SUCCESS_MATCH_TYPES and page_regions:
            hits.append((page_number, match_type, page_regions))
    if not hits:
        return _empty_quote_map("not_on_page")
    hits.sort(key=lambda item: (_region_area(item[2]), len(item[2]), item[0]))
    _, match_type, regions = hits[0]
    pages = sorted({int(item["page"]) for item in regions})
    return {
        "quote_highlight_available": True,
        "regions": regions,
        "match_type": match_type,
        "pages": pages,
    }


def map_quote_to_regions(
    quote: str,
    *,
    chunk_text: str,
    layouts: dict[int, PageLayout],
    page_start: int,
    page_end: int,
    ranges: list[dict[str, Any]] | None = None,
    segments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Map a verbatim quote onto PDF span boxes for one cited chunk.

    The quote must compact-match the chunk text. Boxes come only from
    map_slice_to_spans; none are invented.
    """
    cleaned = re.sub(r"\s+", " ", (quote or "").strip())
    if not cleaned or not compact_contains(chunk_text or "", cleaned):
        return _empty_quote_map("not_in_chunk")

    segment_matches = _find_matching_segments(cleaned, segments)
    if segment_matches:
        highlighted = [row for row in segment_matches if row.get("highlight_available")]
        if highlighted:
            # Prefer the tightest segment (fewest regions / shortest text).
            chosen = min(
                highlighted,
                key=lambda row: (
                    len(row.get("regions") or []),
                    len(row.get("text") or ""),
                ),
            )
            regions = chosen.get("regions") or []
            if regions:
                pages = sorted(
                    {
                        int(item["page"])
                        for item in regions
                        if isinstance(item, dict) and item.get("page") is not None
                    }
                )
                return {
                    "quote_highlight_available": True,
                    "regions": regions,
                    "match_type": str(chosen.get("match_type") or "exact"),
                    "pages": pages or chosen.get("pages") or [],
                    "segment_index": chosen.get("index"),
                }

    if not layouts:
        return _empty_quote_map("no_layout")

    page_rows: list[dict[str, Any]] = []
    range_rows = [
        row
        for row in (ranges or [])
        if isinstance(row, dict) and row.get("page") in layouts
    ]
    if range_rows:
        for row in sorted(range_rows, key=lambda item: int(item["page"])):
            page_number = int(row["page"])
            layout = layouts[page_number]
            try:
                start = max(0, int(row.get("char_start") if row.get("char_start") is not None else row.get("page_char_start") or 0))
                end = int(row.get("char_end") if row.get("char_end") is not None else row.get("page_char_end") or 0)
            except (TypeError, ValueError):
                start, end = 0, 0
            if end > start:
                text = layout.plain[start:end]
            else:
                text = _layout_search_text(layout)
            if not text.strip():
                text = _layout_search_text(layout)
            if text.strip():
                page_rows.append({"page_number": page_number, "text": text})
    if not page_rows:
        for page_number in range(int(page_start), int(page_end) + 1):
            layout = layouts.get(page_number)
            if not layout:
                continue
            text = _layout_search_text(layout)
            if text.strip():
                page_rows.append({"page_number": page_number, "text": text})
    if not page_rows:
        return _map_quote_via_page_spans(cleaned, layouts, page_start, page_end)

    window, page_spans = build_document_text(page_rows)
    slices, _, _, fully = locate_chunk_slices(cleaned, window, page_spans, 0)
    if not fully or not slices:
        # Compact locate: quote may differ in whitespace from the page window.
        hay_c, hay_orig = compact(window)
        needle_c, _ = compact(cleaned)
        at = hay_c.find(needle_c) if needle_c else -1
        if at == -1:
            hyphen_span = _hyphen_compact_span(window, cleaned)
            if hyphen_span is None:
                return _map_quote_via_page_spans(
                    cleaned, layouts, page_start, page_end
                )
            start, end = hyphen_span
        else:
            start = hay_orig[at]
            end = hay_orig[at + len(needle_c) - 1] + 1
        slices = split_range_by_pages(start, end, page_spans, window)
        if not slices:
            return _map_quote_via_page_spans(cleaned, layouts, page_start, page_end)

    regions, match_type = _map_slices_to_regions(slices, layouts)
    if not regions:
        return _map_quote_via_page_spans(cleaned, layouts, page_start, page_end)
    pages = sorted({int(item["page"]) for item in regions})
    return {
        "quote_highlight_available": True,
        "regions": regions,
        "match_type": match_type,
        "pages": pages,
    }


def map_chunk_to_evidence(
    chunk: dict[str, Any],
    *,
    document_id: str,
    full_text: str,
    page_spans: list[tuple[int, int, int]],
    layouts: dict[int, PageLayout],
    search_from: int,
    text_engine: str,
    page_engines: dict[int, str] | None = None,
) -> tuple[dict[str, Any], int]:
    slices, next_from, join_recovered, fully_located = locate_chunk_slices(
        chunk["text"],
        full_text,
        page_spans,
        search_from,
    )

    part_results: list[dict[str, Any]] = []
    regions: list[dict[str, Any]] = []
    ranges: list[dict[str, Any]] = []
    match_types: list[str] = []

    nonempty_slices = 0
    nonempty_success = 0

    for slice_row in slices:
        page_number = int(slice_row["page"])
        layout = layouts.get(page_number)
        if layout is None:
            mapped = {
                "match_type": "failed",
                "confidence": 0.0,
                "bbox_count": 0,
                "regions": [],
                "notes": "missing page layout",
            }
        else:
            mapped = map_slice_to_spans(
                slice_row["text"],
                layout.spans,
                layout.plain,
            )
        match_type = mapped["match_type"]
        match_types.append(match_type)
        page_regions = _regions_for_page(page_number, mapped.get("regions") or [])
        regions.extend(page_regions)
        ranges.append(
            {
                "page": page_number,
                "char_start": slice_row.get("page_char_start"),
                "char_end": slice_row.get("page_char_end"),
                "match_type": match_type,
            }
        )
        part_results.append(
            {
                "page": page_number,
                "match_type": match_type,
                "bbox_count": len(page_regions),
                "notes": mapped.get("notes") or "",
            }
        )
        if slice_row["text"].strip():
            nonempty_slices += 1
            if match_type in SUCCESS_MATCH_TYPES and page_regions:
                nonempty_success += 1

    if match_types:
        rank = {
            "failed": 0,
            "empty_slice": 1,
            "hyphen_fuzzy": 2,
            "fuzzy_compact": 3,
            "normalized": 4,
            "exact": 5,
        }
        overall_type = min(match_types, key=lambda item: rank.get(item, 0))
    else:
        overall_type = "failed"

    highlight_available = (
        fully_located
        and nonempty_slices > 0
        and nonempty_success == nonempty_slices
        and bool(regions)
    )
    if not highlight_available:
        # Drop incomplete rects so Phase 2 cannot treat a partial map as exact.
        if not fully_located or nonempty_success != nonempty_slices:
            regions = []

    pages = [int(row["page"]) for row in slices] or [
        int(chunk.get("page_start") or chunk.get("page_number") or 1)
    ]
    if page_engines:
        if any(
            "ocr" in str(page_engines.get(page_number) or text_engine).lower()
            for page_number in pages
        ):
            text_engine = OCR_ENGINE
            highlight_available = False
            regions = []
    if slices:
        sources = {
            (layouts[p].source if p in layouts else SOURCE_NONE)
            for p in pages
        }
        layout_source = SOURCE_NATIVE if sources == {SOURCE_NATIVE} else SOURCE_NONE
    else:
        layout_source = SOURCE_NONE

    primary_layout = layouts.get(min(pages)) if pages else None
    image_count = int(getattr(primary_layout, "image_count", 0) or 0)
    span_count = len(primary_layout.spans) if primary_layout is not None else None

    record = {
        "chunk_id": chunk["chunk_id"],
        "document_id": document_id,
        "page_start": min(pages),
        "page_end": max(pages),
        "snippet": make_snippet(chunk.get("text") or ""),
        "highlight_available": highlight_available,
        "match_type": overall_type if slices else "failed",
        "source": layout_source,
        "text_engine": text_engine,
        "layout_engine": PRIMARY_ENGINE,
        "join_recovered": join_recovered,
        "ranges": ranges,
        "regions": regions,
        "parts": part_results,
        "segments": build_sentence_segments(
            chunk.get("text") or "",
            layouts=layouts,
            page_start=min(pages),
            page_end=max(pages),
            ranges=ranges,
        ),
        "content_type": infer_content_type(
            chunk.get("text") or "",
            highlight_available=highlight_available,
            layout_source=layout_source,
            text_engine=text_engine,
            image_count=image_count,
            span_count=span_count,
        ),
    }
    return record, next_from


def page_layout_records(layouts: dict[int, PageLayout]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page_number in sorted(layouts):
        layout = layouts[page_number]
        rows.append(
            {
                "page_number": layout.page_number,
                "width": layout.width,
                "height": layout.height,
                "source": layout.source,
                "engine": layout.engine,
                "span_count": len(layout.spans),
            }
        )
    return rows


def build_document_evidence(
    pdf_path: str,
    document_id: str,
    pages: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    *,
    text_engine: str,
) -> dict[str, Any]:
    """
    Build persistable evidence for one document.

    `pages` and `chunks` must be the same objects produced by the existing
    extraction/chunking pipeline.
    """
    layouts = extract_page_layouts(pdf_path)
    full_text, page_spans = build_document_text(pages)
    page_engines = {
        int(page["page_number"]): str(page.get("text_engine") or text_engine)
        for page in pages
        if page.get("page_number") is not None
    }
    search_from = 0
    chunk_rows: list[dict[str, Any]] = []
    highlighted = 0
    for chunk in chunks:
        record, search_from = map_chunk_to_evidence(
            chunk,
            document_id=document_id,
            full_text=full_text,
            page_spans=page_spans,
            layouts=layouts,
            search_from=search_from,
            text_engine=text_engine,
            page_engines=page_engines,
        )
        if record["highlight_available"]:
            highlighted += 1
        chunk_rows.append(record)

    logger.info(
        "evidence_mapping document_id=%s chunks=%s highlighted=%s engine=%s",
        document_id,
        len(chunk_rows),
        highlighted,
        text_engine,
    )
    return {
        "pages": page_layout_records(layouts),
        "chunks": chunk_rows,
    }
