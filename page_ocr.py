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
OCR_DPI = 200
OCR_MAX_EDGE = 1600
OCR_MIN_CHARS = 40
OCR_TIMEOUT_SEC = 8
OCR_MAX_PAGES = 150
OCR_GIVE_UP_AFTER = 8
OCR_LANG = "eng"
OCR_TESSERACT_CONFIG = "--oem 1 --psm 6"

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
        if _strip_char_count(existing.get("text")) < min_chars:
            needed.append(page_number)
    return needed


def _render_page_gray(page: Any):
    import pymupdf as fitz

    zoom = OCR_DPI / 72.0
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


def ocr_pixmap(pixmap: Any) -> str:
    import pytesseract
    from PIL import Image

    image = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)
    try:
        text = pytesseract.image_to_string(
            image,
            lang=OCR_LANG,
            timeout=OCR_TIMEOUT_SEC,
            config=OCR_TESSERACT_CONFIG,
        )
    finally:
        image.close()
    return (text or "").strip()


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
                stats["skipped_no_image"] += 1
                continue

            stats["ran"] += 1
            pixmap = None
            text = ""
            try:
                pixmap = _render_page_gray(page)
                text = ocr_pixmap(pixmap)
            except Exception:
                logger.warning(
                    "page_ocr document_id=%s page=%s failed",
                    document_id or "unknown",
                    page_number,
                    exc_info=True,
                )
            finally:
                pixmap = None

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
