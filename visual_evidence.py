"""
Figure, table, and image evidence policy.

Native-text quotes keep real span highlights. Visual content is shown as a
page (plus caption/snippet) unless a tight, real text box was mapped.
Geometry is never invented.
"""

from __future__ import annotations

from typing import Any

TYPE_NATIVE_TEXT = "native_text"
TYPE_FIGURE_CAPTION = "figure_caption"
TYPE_TABLE = "table"
TYPE_SCANNED_OR_IMAGE = "scanned_or_image"
TYPE_SCANNED_OCR = "scanned_ocr"
TYPE_LOW_TEXT_LAYOUT = "low_text_layout"

SCAN_TYPES = frozenset(
    {TYPE_SCANNED_OR_IMAGE, TYPE_SCANNED_OCR, TYPE_LOW_TEXT_LAYOUT}
)
VISUAL_TYPES = frozenset({TYPE_FIGURE_CAPTION, TYPE_TABLE}) | SCAN_TYPES

# Caption lines are short. A taller box almost always covers the graphic.
_MAX_FIGURE_BOX_HEIGHT = 72.0
# Whole-page table dumps are not a "minimum highlight span".
_MAX_TABLE_AREA_RATIO = 0.40
_DEFAULT_PAGE_AREA = 612.0 * 792.0

_KEEP_STATUSES = frozenset(
    {
        "not_in_chunk",
        "rejected",
        "none",
        "no_evidence_data",
        "failed",
    }
)


def _region_height(region: dict[str, Any]) -> float:
    try:
        return max(0.0, float(region.get("y1") or 0) - float(region.get("y0") or 0))
    except (TypeError, ValueError):
        return 0.0


def _region_area(region: dict[str, Any]) -> float:
    try:
        width = max(0.0, float(region.get("x1") or 0) - float(region.get("x0") or 0))
        return width * _region_height(region)
    except (TypeError, ValueError):
        return 0.0


def _union_height(regions: list[dict[str, Any]]) -> float:
    ys0: list[float] = []
    ys1: list[float] = []
    for item in regions:
        try:
            ys0.append(float(item.get("y0") or 0))
            ys1.append(float(item.get("y1") or 0))
        except (TypeError, ValueError):
            continue
    if not ys0 or not ys1:
        return 0.0
    return max(0.0, max(ys1) - min(ys0))


def quote_regions_are_safe(
    content_type: str,
    regions: list[dict[str, Any]],
    *,
    page_width: float | None = None,
    page_height: float | None = None,
) -> bool:
    """True when existing boxes are tight enough to paint for this content type."""
    if not regions:
        return False
    kind = (content_type or "").strip()
    if kind in SCAN_TYPES:
        return False
    if kind == TYPE_FIGURE_CAPTION:
        return _union_height(regions) <= _MAX_FIGURE_BOX_HEIGHT
    if kind == TYPE_TABLE:
        area = sum(_region_area(item) for item in regions)
        page_area = (
            float(page_width) * float(page_height)
            if page_width and page_height and page_width > 0 and page_height > 0
            else _DEFAULT_PAGE_AREA
        )
        return area <= page_area * _MAX_TABLE_AREA_RATIO
    return True


def apply_visual_highlight_policy(
    payload: dict[str, Any],
    *,
    page_width: float | None = None,
    page_height: float | None = None,
) -> dict[str, Any]:
    """
    Strip paint flags for visual evidence that has no honest text box.

    Stored regions are left in the payload; highlight_available / quote
    highlight flags decide what the UI may draw.
    """
    kind = str(payload.get("content_type") or "")
    if kind not in VISUAL_TYPES:
        return payload

    out = dict(payload)
    quote_regions = [
        item for item in (out.get("quote_regions") or []) if isinstance(item, dict)
    ]
    quote_ok = bool(out.get("quote_highlight_available")) and bool(quote_regions)
    status = str(out.get("quote_mapping_status") or "none")

    if kind in SCAN_TYPES:
        out["highlight_available"] = False
        out["quote_highlight_available"] = False
        out["quote_regions"] = []
        # Only rewrite status when a highlight was claimed. Sentence/claim
        # localization without boxes should stay as-is.
        if quote_ok and status not in _KEEP_STATUSES:
            out["quote_mapping_status"] = "no_layout"
        return out

    # Figures and tables: never paint the whole chunk as a stand-in for the graphic.
    out["highlight_available"] = False

    if quote_ok and quote_regions_are_safe(
        kind,
        quote_regions,
        page_width=page_width,
        page_height=page_height,
    ):
        return out

    out["quote_highlight_available"] = False
    out["quote_regions"] = []
    if quote_ok and status not in _KEEP_STATUSES:
        out["quote_mapping_status"] = "fallback_chunk"
    return out
