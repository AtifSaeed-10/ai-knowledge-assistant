"""
PDF text extraction for the indexing pipeline.

PyMuPDF is the primary extractor; pypdf is the fallback when the primary
yields little or no text. Image-only pages then get a Tesseract pass.
Both native extractors read page-by-page from disk without loading the
whole file into Python memory.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from page_ocr import OCR_ENGINE, fill_low_text_pages_with_ocr

logger = logging.getLogger(__name__)

# Below this total stripped-character count, the fallback extractor is tried.
MIN_PRIMARY_CHARS = 50

PRIMARY_ENGINE = "pymupdf"
FALLBACK_ENGINE = "pypdf"

PageDict = dict[str, Any]
PageDiagnostic = dict[str, Any]


@dataclass
class ExtractionResult:
    pages: list[PageDict]
    engine_used: str
    total_pages: int
    pages_with_text: int
    total_chars: int
    primary_chars: int
    fallback_chars: int
    tried_fallback: bool
    tried_ocr: bool = False
    ocr_pages: int = 0
    per_page: list[PageDiagnostic] = field(default_factory=list)


def _strip_char_count(text: str | None) -> int:
    return len((text or "").strip())


def extract_pages_with_pymupdf(pdf_path: str) -> tuple[list[PageDict], list[PageDiagnostic]]:
    import pymupdf as fitz

    pages: list[PageDict] = []
    diagnostics: list[PageDiagnostic] = []

    doc = fitz.open(pdf_path)
    try:
        total_pages = doc.page_count
        for index in range(total_pages):
            page_number = index + 1
            page = doc.load_page(index)
            text = page.get_text("text") or ""
            char_count = _strip_char_count(text)

            diagnostics.append(
                {
                    "page": page_number,
                    "engine": PRIMARY_ENGINE,
                    "chars": char_count,
                    "total_pages": total_pages,
                }
            )

            if char_count:
                pages.append(
                    {
                        "page_number": page_number,
                        "text": text,
                        "text_engine": PRIMARY_ENGINE,
                    }
                )
    finally:
        doc.close()

    return pages, diagnostics


def extract_pages_with_pypdf(pdf_path: str) -> tuple[list[PageDict], list[PageDiagnostic]]:
    from pypdf import PdfReader

    pages: list[PageDict] = []
    diagnostics: list[PageDiagnostic] = []

    reader = PdfReader(pdf_path, strict=False)
    total_pages = len(reader.pages)

    for page_number, page in enumerate(reader.pages, start=1):
        text = ""
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        if not _strip_char_count(text):
            try:
                text = page.extract_text(extraction_mode="layout") or ""
            except (TypeError, KeyError):
                pass
            except Exception:
                pass

        char_count = _strip_char_count(text)
        diagnostics.append(
            {
                "page": page_number,
                "engine": FALLBACK_ENGINE,
                "chars": char_count,
                "total_pages": total_pages,
            }
        )

        if char_count:
            pages.append(
                {
                    "page_number": page_number,
                    "text": text,
                    "text_engine": FALLBACK_ENGINE,
                }
            )

    return pages, diagnostics


def _total_chars(pages: list[PageDict]) -> int:
    return sum(_strip_char_count(page.get("text")) for page in pages)


def _tag_pages(pages: list[PageDict], engine: str) -> list[PageDict]:
    tagged: list[PageDict] = []
    for page in pages:
        row = dict(page)
        row["text_engine"] = row.get("text_engine") or engine
        tagged.append(row)
    return tagged


def _engine_used(pages: list[PageDict], default: str) -> str:
    engines = {
        str(page.get("text_engine") or default)
        for page in pages
        if _strip_char_count(page.get("text"))
    }
    if not engines:
        return default
    if engines == {OCR_ENGINE}:
        return OCR_ENGINE
    if OCR_ENGINE in engines:
        return f"{default}+{OCR_ENGINE}"
    if len(engines) == 1:
        return next(iter(engines))
    return default


def _log_page_diagnostics(
    diagnostics: list[PageDiagnostic],
    *,
    document_id: str | None = None,
) -> None:
    doc_label = document_id or "unknown"
    for entry in diagnostics:
        logger.info(
            "pdf_extract document_id=%s page=%s/%s engine=%s chars=%s",
            doc_label,
            entry.get("page"),
            entry.get("total_pages"),
            entry.get("engine"),
            entry.get("chars"),
        )


def extract_pages_from_pdf(
    pdf_path: str,
    *,
    document_id: str | None = None,
    min_primary_chars: int = MIN_PRIMARY_CHARS,
    on_progress: Any | None = None,
) -> ExtractionResult:
    """
    Extract page text using PyMuPDF, falling back to pypdf when the primary
    result is insufficient. Image pages that still have almost no text are
    OCR'd with Tesseract. Returns the better native extract, plus any OCR
    fills.
    """
    primary_pages, primary_diag = extract_pages_with_pymupdf(pdf_path)
    primary_chars = _total_chars(primary_pages)

    _log_page_diagnostics(primary_diag, document_id=document_id)

    fallback_pages: list[PageDict] = []
    fallback_diag: list[PageDiagnostic] = []
    fallback_chars = 0
    tried_fallback = False

    if primary_chars < min_primary_chars:
        tried_fallback = True
        logger.info(
            "pdf_extract document_id=%s primary=%s chars=%s below threshold=%s; "
            "trying fallback=%s",
            document_id or "unknown",
            PRIMARY_ENGINE,
            primary_chars,
            min_primary_chars,
            FALLBACK_ENGINE,
        )
        fallback_pages, fallback_diag = extract_pages_with_pypdf(pdf_path)
        fallback_chars = _total_chars(fallback_pages)
        _log_page_diagnostics(fallback_diag, document_id=document_id)

    if tried_fallback and fallback_chars > primary_chars:
        chosen_pages = _tag_pages(fallback_pages, FALLBACK_ENGINE)
        native_engine = FALLBACK_ENGINE
        per_page = fallback_diag
        total_pages = fallback_diag[0]["total_pages"] if fallback_diag else 0
    else:
        chosen_pages = _tag_pages(primary_pages, PRIMARY_ENGINE)
        native_engine = PRIMARY_ENGINE
        per_page = primary_diag
        total_pages = primary_diag[0]["total_pages"] if primary_diag else 0

    if on_progress and total_pages:
        on_progress({"total_pages": total_pages, "ran": 0, "filled": 0})

    chosen_pages, ocr_stats = fill_low_text_pages_with_ocr(
        pdf_path,
        chosen_pages,
        total_pages,
        document_id=document_id,
        on_progress=on_progress,
    )
    engine_used = _engine_used(chosen_pages, native_engine)
    total_chars = _total_chars(chosen_pages)

    logger.info(
        "pdf_extract document_id=%s summary engine=%s total_pages=%s "
        "pages_with_text=%s total_chars=%s primary_chars=%s fallback_chars=%s "
        "tried_fallback=%s tried_ocr=%s ocr_pages=%s",
        document_id or "unknown",
        engine_used,
        total_pages,
        len(chosen_pages),
        total_chars,
        primary_chars,
        fallback_chars,
        tried_fallback,
        bool(ocr_stats.get("tried")),
        int(ocr_stats.get("filled") or 0),
    )

    return ExtractionResult(
        pages=chosen_pages,
        engine_used=engine_used,
        total_pages=total_pages,
        pages_with_text=len(chosen_pages),
        total_chars=total_chars,
        primary_chars=primary_chars,
        fallback_chars=fallback_chars,
        tried_fallback=tried_fallback,
        tried_ocr=bool(ocr_stats.get("tried")),
        ocr_pages=int(ocr_stats.get("filled") or 0),
        per_page=per_page,
    )


INDEX_FAILURE_NO_TEXT = (
    "No searchable text could be extracted from this PDF. "
    "If this is a scan, the pages may be too blurry, or OCR could not read them."
)
