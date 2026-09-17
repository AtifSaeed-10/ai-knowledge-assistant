"""
Per-page OCR fallback for scanned PDFs.

Native text extraction stays first. Tesseract runs only on pages that look
like scans (embedded images) and yielded almost no text. Digital PDFs, blank
pages, and already-searchable files skip this path entirely.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

OCR_ENGINE = "tesseract-ocr"
OCR_DPI = 220
OCR_RETRY_DPI = 280
OCR_BLANK_DPI = 72
OCR_MAX_EDGE = 1800
OCR_MIN_CHARS = 40
OCR_TIMEOUT_SEC = 15
OCR_MAX_PAGES = 200
OCR_GIVE_UP_AFTER = 8
OCR_LANG = "eng"
OCR_TESSERACT_CONFIGS = ("--oem 1 --psm 4", "--oem 1 --psm 6")
OCR_RETRY_CONFIG = "--oem 1 --psm 3"
OCR_MIN_LETTER_RATIO = 0.35

PageDict = dict[str, Any]

_tesseract_ok: bool | None = None


def tesseract_available() -> bool:
    """True when the Tesseract binary can be invoked. Cached for the process."""
    global _tesseract_ok
    if _tesseract_ok is not None:
        return _tesseract_ok
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        _tesseract_ok = True
    except Exception:
        _tesseract_ok = False
        logger.warning("page_ocr tesseract unavailable; scanned pages will stay unreadable")
    return _tesseract_ok


def reset_tesseract_cache() -> None:
    """Test helper."""
    global _tesseract_ok
    _tesseract_ok = None


def _strip_char_count(text: str | None) -> int:
    return len((text or "").strip())


def text_is_searchable(text: str | None, *, min_chars: int = OCR_MIN_CHARS) -> bool:
    """True when native extract already has enough real letters to search."""
    stripped = (text or "").strip()
    if len(stripped) < min_chars:
        return False
    letters = sum(ch.isalpha() for ch in stripped)
    if letters < max(12, min_chars // 2):
        return False
    return (letters / len(stripped)) >= OCR_MIN_LETTER_RATIO


def page_has_images(page: Any) -> bool:
    try:
        return bool(page.get_images())
    except Exception:
        return False


def pages_needing_ocr(
    pages: list[PageDict],
    total_pages: int,
    *,
    min_chars: int = OCR_MIN_CHARS,
) -> list[int]:
    """Page numbers that have too little extracted text to search."""
    by_page = {int(item["page_number"]): item for item in pages if item.get("page_number")}
    needed: list[int] = []
    for page_number in range(1, max(total_pages, 0) + 1):
        existing = by_page.get(page_number) or {}
        if not text_is_searchable(existing.get("text"), min_chars=min_chars):
            needed.append(page_number)
    return needed


def _render_page_gray(page: Any, *, dpi: int = OCR_DPI):
    import pymupdf as fitz

    zoom = dpi / 72.0
    width = float(page.rect.width) * zoom
    height = float(page.rect.height) * zoom
    longest = max(width, height, 1.0)
    if longest > OCR_MAX_EDGE:
        zoom *= OCR_MAX_EDGE / longest
    pixmap = page.get_pixmap(
        matrix=fitz.Matrix(zoom, zoom),
        colorspace=fitz.csGRAY,
        alpha=False,
    )
    return pixmap


def _pixmap_looks_blank(pixmap: Any, *, ink_ratio: float = 0.012) -> bool:
    """Cheap ink check so blank digital pages skip Tesseract."""
    samples = getattr(pixmap, "samples", None) or b""
    if not samples:
        return True
    step = max(1, len(samples) // 20000)
    checked = 0
    dark = 0
    for index in range(0, len(samples), step):
        checked += 1
        if samples[index] < 240:
            dark += 1
    if checked == 0:
        return True
    return (dark / checked) < ink_ratio


def ocr_pixmap(pixmap: Any, *, config: str | None = None) -> str:
    import pytesseract
    from PIL import Image

    image = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)
    try:
        text = pytesseract.image_to_string(
            image,
            lang=OCR_LANG,
            timeout=OCR_TIMEOUT_SEC,
            config=config or OCR_TESSERACT_CONFIGS[0],
        )
    finally:
        image.close()
    return (text or "").strip()


def ocr_page_text(page: Any) -> str:
    """Try column layout, then uniform block, then a sharper render."""
    best = ""
    pixmap = None
    try:
        pixmap = _render_page_gray(page, dpi=OCR_DPI)
        for config in OCR_TESSERACT_CONFIGS:
            text = ocr_pixmap(pixmap, config=config)
            if _strip_char_count(text) > _strip_char_count(best):
                best = text
            if _strip_char_count(best) >= OCR_MIN_CHARS:
                return best
    finally:
        pixmap = None

    retry = None
    try:
        retry = _render_page_gray(page, dpi=OCR_RETRY_DPI)
        for config in (OCR_TESSERACT_CONFIGS[0], OCR_RETRY_CONFIG):
            text = ocr_pixmap(retry, config=config)
            if _strip_char_count(text) > _strip_char_count(best):
                best = text
            if _strip_char_count(best) >= OCR_MIN_CHARS:
                return best
    finally:
        retry = None
    return best


def fill_low_text_pages_with_ocr(
    pdf_path: str,
    pages: list[PageDict],
    total_pages: int,
    *,
    document_id: str | None = None,
    on_progress: Any | None = None,
) -> tuple[list[PageDict], dict[str, Any]]:
    """
    OCR image pages that native extractors left empty or nearly empty.

    Returns (pages, stats). Pages that already have enough text are unchanged.
    """
    stats = {
        "tried": False,
        "available": False,
        "candidates": 0,
        "ran": 0,
        "filled": 0,
        "skipped_no_image": 0,
        "stopped_early": False,
    }
    needed = pages_needing_ocr(pages, total_pages)
    stats["candidates"] = len(needed)
    if not needed:
        return pages, stats

    if not tesseract_available():
        return pages, stats
    stats["available"] = True
    stats["tried"] = True

    by_page = {int(item["page_number"]): dict(item) for item in pages if item.get("page_number")}
    work = needed[:OCR_MAX_PAGES]
    if len(needed) > OCR_MAX_PAGES:
        logger.warning(
            "page_ocr document_id=%s capping OCR pages at %s of %s",
            document_id or "unknown",
            OCR_MAX_PAGES,
            len(needed),
        )

    import pymupdf as fitz

    doc = fitz.open(pdf_path)
    hits = 0
    try:
        for page_number in work:
            index = page_number - 1
            if index < 0 or index >= doc.page_count:
                continue
            page = doc.load_page(index)
            if not page_has_images(page):
                try:
                    probe = _render_page_gray(page, dpi=OCR_BLANK_DPI)
                    blank = _pixmap_looks_blank(probe)
                except Exception:
                    blank = True
                if blank:
                    stats["skipped_no_image"] += 1
                    continue

            stats["ran"] += 1
            text = ""
            try:
                text = ocr_page_text(page)
            except Exception:
                logger.warning(
                    "page_ocr document_id=%s page=%s failed",
                    document_id or "unknown",
                    page_number,
                    exc_info=True,
                )

            existing = by_page.get(page_number) or {}
            if _strip_char_count(text) > _strip_char_count(existing.get("text")):
                hits += 1
                stats["filled"] += 1
                by_page[page_number] = {
                    "page_number": page_number,
                    "text": text,
                    "text_engine": OCR_ENGINE,
                }

            if stats["ran"] >= OCR_GIVE_UP_AFTER and hits == 0 and len(needed) <= OCR_GIVE_UP_AFTER + 4:
                stats["stopped_early"] = True
                logger.info(
                    "page_ocr document_id=%s stopping after %s unreadable scan pages",
                    document_id or "unknown",
                    stats["ran"],
                )
                break
            if on_progress and (stats["ran"] == 1 or stats["ran"] % 5 == 0):
                on_progress(
                    {
                        "total_pages": total_pages,
                        "ran": stats["ran"],
                        "filled": stats["filled"],
                    }
                )
    finally:
        doc.close()

    logger.info(
        "page_ocr document_id=%s candidates=%s ran=%s filled=%s skipped_no_image=%s stopped_early=%s",
        document_id or "unknown",
        stats["candidates"],
        stats["ran"],
        stats["filled"],
        stats["skipped_no_image"],
        stats["stopped_early"],
    )

    merged = [by_page[number] for number in sorted(by_page)]
    return merged, stats
