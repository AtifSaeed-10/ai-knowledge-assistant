"""Per-page OCR fallback: only image pages with almost no native text."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from unittest.mock import patch

import pymupdf as fitz
from PIL import Image

from page_ocr import (
    OCR_ENGINE,
    OCR_GIVE_UP_AFTER,
    fill_low_text_pages_with_ocr,
    pages_needing_ocr,
    reset_tesseract_cache,
    text_is_searchable,
)
from pdf_extraction import PRIMARY_ENGINE, extract_pages_from_pdf
from evidence_mapping import SOURCE_NONE, infer_content_type, map_chunk_to_evidence


def _write_text_pdf(path: str, page_texts: list[str]) -> None:
    doc = fitz.open()
    try:
        for text in page_texts:
            page = doc.new_page()
            page.insert_text((72, 72), text)
        doc.save(path)
    finally:
        doc.close()


def _write_blank_pdf(path: str) -> None:
    payload = (
        b"%PDF-1.1\n"
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n"
        b"trailer<< /Root 1 0 R /Size 4 >>\nstartxref\n0\n%%EOF\n"
    )
    with open(path, "wb") as handle:
        handle.write(payload)


def _png_bytes() -> bytes:
    image = Image.new("L", (240, 80), 255)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _write_image_pdf(path: str, page_count: int = 1) -> None:
    png = _png_bytes()
    doc = fitz.open()
    try:
        for _ in range(page_count):
            page = doc.new_page(width=300, height=200)
            page.insert_image(page.rect, stream=png)
        doc.save(path)
    finally:
        doc.close()


def _write_mixed_pdf(path: str) -> None:
    png = _png_bytes()
    doc = fitz.open()
    try:
        text_page = doc.new_page()
        text_page.insert_text(
            (72, 72),
            "Chapter 1: Introduction to force and motion in science class eight.",
        )
        image_page = doc.new_page(width=300, height=200)
        image_page.insert_image(image_page.rect, stream=png)
        doc.save(path)
    finally:
        doc.close()


class TestPagesNeedingOcr(unittest.TestCase):
    def test_empty_and_short_pages_are_candidates(self):
        pages = [{"page_number": 1, "text": "plenty of searchable native text on this page"}]
        self.assertEqual(pages_needing_ocr(pages, 2), [2])
        self.assertEqual(pages_needing_ocr(pages, 1), [])

    def test_garbage_letters_are_not_searchable(self):
        garbage = "~~~~ #### **** ~~~~ #### **** ~~~~ #### ****"
        self.assertFalse(text_is_searchable(garbage))
        pages = [{"page_number": 1, "text": garbage}]
        self.assertEqual(pages_needing_ocr(pages, 1), [1])


class TestFillLowTextPages(unittest.TestCase):
    def setUp(self):
        reset_tesseract_cache()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = self._tmpdir.name

    def tearDown(self):
        reset_tesseract_cache()
        self._tmpdir.cleanup()

    def test_blank_digital_pdf_does_not_ocr(self):
        path = os.path.join(self.tmp, "blank.pdf")
        _write_blank_pdf(path)
        with patch("page_ocr.tesseract_available", return_value=True), patch(
            "page_ocr.ocr_pixmap"
        ) as mock_ocr:
            pages, stats = fill_low_text_pages_with_ocr(path, [], 1)
        mock_ocr.assert_not_called()
        self.assertEqual(pages, [])
        self.assertEqual(stats["filled"], 0)
        self.assertGreaterEqual(stats["skipped_no_image"], 1)

    def test_image_page_uses_ocr_text(self):
        path = os.path.join(self.tmp, "scan.pdf")
        _write_image_pdf(path)
        ocr_text = "Supervised learning trains models from labeled examples."
        with patch("page_ocr.tesseract_available", return_value=True), patch(
            "page_ocr.ocr_page_text", return_value=ocr_text
        ):
            pages, stats = fill_low_text_pages_with_ocr(path, [], 1)
        self.assertEqual(stats["filled"], 1)
        self.assertEqual(pages[0]["text"], ocr_text)
        self.assertEqual(pages[0]["text_engine"], OCR_ENGINE)

    def test_native_text_is_not_replaced(self):
        path = os.path.join(self.tmp, "native.pdf")
        sample = "Chapter 1: Introduction to force and motion in science class eight."
        _write_text_pdf(path, [sample])
        native = [{"page_number": 1, "text": sample, "text_engine": PRIMARY_ENGINE}]
        with patch("page_ocr.tesseract_available", return_value=True), patch(
            "page_ocr.ocr_pixmap"
        ) as mock_ocr:
            pages, stats = fill_low_text_pages_with_ocr(path, native, 1)
        mock_ocr.assert_not_called()
        self.assertEqual(pages[0]["text"], sample)
        self.assertEqual(stats["candidates"], 0)

    def test_gives_up_after_unreadable_scans(self):
        path = os.path.join(self.tmp, "covers.pdf")
        _write_image_pdf(path, page_count=OCR_GIVE_UP_AFTER + 3)
        with patch("page_ocr.tesseract_available", return_value=True), patch(
            "page_ocr.ocr_page_text", return_value=""
        ) as mock_ocr:
            pages, stats = fill_low_text_pages_with_ocr(path, [], OCR_GIVE_UP_AFTER + 3)
        self.assertTrue(stats["stopped_early"])
        self.assertEqual(mock_ocr.call_count, OCR_GIVE_UP_AFTER)
        self.assertEqual(pages, [])

    def test_full_book_keeps_ocr_after_cover_pages(self):
        path = os.path.join(self.tmp, "book.pdf")
        page_count = 40
        _write_image_pdf(path, page_count=page_count)
        calls = {"n": 0}

        def fake_ocr(_page):
            calls["n"] += 1
            if calls["n"] <= OCR_GIVE_UP_AFTER:
                return ""
            return "Gregor Samsa woke from uneasy dreams."

        with patch("page_ocr.tesseract_available", return_value=True), patch(
            "page_ocr.ocr_page_text", side_effect=fake_ocr
        ):
            pages, stats = fill_low_text_pages_with_ocr(path, [], page_count)
        self.assertFalse(stats["stopped_early"])
        self.assertGreater(stats["filled"], 0)
        self.assertTrue(any("Gregor" in page["text"] for page in pages))

    def test_missing_tesseract_is_a_no_op(self):
        path = os.path.join(self.tmp, "scan-no-tess.pdf")
        _write_image_pdf(path)
        with patch("page_ocr.tesseract_available", return_value=False), patch(
            "page_ocr.ocr_pixmap"
        ) as mock_ocr:
            pages, stats = fill_low_text_pages_with_ocr(path, [], 1)
        mock_ocr.assert_not_called()
        self.assertFalse(stats["tried"])
        self.assertEqual(pages, [])

    def test_flattened_scan_without_image_xobject_still_ocr(self):
        path = os.path.join(self.tmp, "flat.pdf")
        _write_blank_pdf(path)
        ocr_text = "One apple lodged in his back after his father threw it."
        with patch("page_ocr.tesseract_available", return_value=True), patch(
            "page_ocr.page_has_images", return_value=False
        ), patch("page_ocr._pixmap_looks_blank", return_value=False), patch(
            "page_ocr.ocr_page_text", return_value=ocr_text
        ):
            pages, stats = fill_low_text_pages_with_ocr(path, [], 1)
        self.assertEqual(stats["filled"], 1)
        self.assertEqual(pages[0]["text"], ocr_text)


class TestExtractPagesOcr(unittest.TestCase):
    def setUp(self):
        reset_tesseract_cache()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = self._tmpdir.name

    def tearDown(self):
        reset_tesseract_cache()
        self._tmpdir.cleanup()

    def test_searchable_pdf_stays_on_pymupdf(self):
        path = os.path.join(self.tmp, "normal.pdf")
        sample = "Chapter 1: Introduction to force and motion in science class eight."
        _write_text_pdf(path, [sample, sample + " Continued on page two."])
        with patch("page_ocr.ocr_pixmap") as mock_ocr:
            result = extract_pages_from_pdf(path)
        mock_ocr.assert_not_called()
        self.assertEqual(result.engine_used, PRIMARY_ENGINE)
        self.assertFalse(result.tried_ocr)
        self.assertEqual(result.ocr_pages, 0)

    def test_scan_and_text_pages_are_merged(self):
        path = os.path.join(self.tmp, "mixed.pdf")
        _write_mixed_pdf(path)
        ocr_text = "Classification and regression are two supervised learning tasks."
        with patch("page_ocr.tesseract_available", return_value=True), patch(
            "page_ocr.ocr_pixmap", return_value=ocr_text
        ):
            result = extract_pages_from_pdf(path)
        self.assertEqual(result.pages_with_text, 2)
        self.assertEqual(result.ocr_pages, 1)
        self.assertIn(OCR_ENGINE, result.engine_used)
        engines = {page["text_engine"] for page in result.pages}
        self.assertIn(PRIMARY_ENGINE, engines)
        self.assertIn(OCR_ENGINE, engines)
        self.assertTrue(any("supervised" in page["text"].lower() for page in result.pages))


class TestOcrContentType(unittest.TestCase):
    def test_ocr_pages_are_not_highlightable(self):
        self.assertEqual(
            infer_content_type(
                "sent him to the Realschule in Linz",
                highlight_available=False,
                layout_source=SOURCE_NONE,
                text_engine=OCR_ENGINE,
            ),
            "scanned_ocr",
        )

    def test_chunk_from_ocr_page_keeps_page_level_citations(self):
        text = "supervised learning uses labeled examples for classification"
        record, _ = map_chunk_to_evidence(
            {
                "chunk_id": "c1",
                "text": text,
                "page_start": 1,
                "page_number": 1,
            },
            document_id="doc-ocr",
            full_text=text,
            page_spans=[(0, len(text), 1)],
            layouts={},
            search_from=0,
            text_engine=PRIMARY_ENGINE,
            page_engines={1: OCR_ENGINE},
        )
        self.assertEqual(record["text_engine"], OCR_ENGINE)
        self.assertFalse(record["highlight_available"])
        self.assertEqual(record["content_type"], "scanned_ocr")
        self.assertEqual(record["regions"], [])


if __name__ == "__main__":
    unittest.main()
