"""Tests for PDF text extraction and indexing failure handling."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pymupdf as fitz

from chunking import MIN_CHUNK_CHARS
from database.db import init_db
from database.document_store import (
    create_document,
    delete_document,
    get_document,
    mark_document_index_failed,
)
from indexer import index_pdf
from pdf_extraction import (
    FALLBACK_ENGINE,
    INDEX_FAILURE_NO_TEXT,
    MIN_PRIMARY_CHARS,
    PRIMARY_ENGINE,
    extract_pages_from_pdf,
    extract_pages_with_pypdf,
    extract_pages_with_pymupdf,
)


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


class TestPdfExtraction(unittest.TestCase):
    def setUp(self):
        init_db()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = self._tmpdir.name

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_normal_text_pdf(self):
        path = os.path.join(self.tmp, "normal.pdf")
        sample = "Chapter 1: Introduction to force and motion in science class eight."
        _write_text_pdf(path, [sample, sample + " Continued on page two."])

        result = extract_pages_from_pdf(path)

        self.assertGreaterEqual(result.total_chars, MIN_PRIMARY_CHARS)
        self.assertEqual(result.pages_with_text, 2)
        self.assertEqual(result.engine_used, PRIMARY_ENGINE)
        self.assertFalse(result.tried_fallback)
        self.assertGreater(len(result.per_page), 0)

    def test_pypdf_fails_but_pymupdf_succeeds(self):
        path = os.path.join(self.tmp, "pymupdf-wins.pdf")
        body = "Photosynthesis converts light energy. " * 12
        _write_text_pdf(path, [body])

        with patch(
            "pdf_extraction.extract_pages_with_pypdf",
            return_value=([], []),
        ):
            result = extract_pages_from_pdf(path, min_primary_chars=999_999)

        self.assertGreater(result.total_chars, MIN_PRIMARY_CHARS)
        self.assertEqual(result.engine_used, PRIMARY_ENGINE)
        self.assertTrue(result.tried_fallback)
        self.assertEqual(result.fallback_chars, 0)

    def test_zero_extractable_text(self):
        path = os.path.join(self.tmp, "blank.pdf")
        _write_blank_pdf(path)

        result = extract_pages_from_pdf(path)

        self.assertEqual(result.total_chars, 0)
        self.assertEqual(result.pages_with_text, 0)

    def test_successful_chunk_creation_after_fallback(self):
        path = os.path.join(self.tmp, "fallback-chunks.pdf")
        long_page = ("Energy cannot be created or destroyed. " * 20).strip()
        _write_text_pdf(path, [long_page])

        empty_primary = (
            [],
            [{"page": 1, "engine": PRIMARY_ENGINE, "chars": 0, "total_pages": 1}],
        )

        with patch(
            "pdf_extraction.extract_pages_with_pymupdf",
            return_value=empty_primary,
        ):
            result = extract_pages_from_pdf(path)

        self.assertEqual(result.engine_used, FALLBACK_ENGINE)
        self.assertTrue(result.tried_fallback)
        self.assertGreater(result.total_chars, MIN_CHUNK_CHARS)

        from chunking import build_chunks_from_pages

        chunks = build_chunks_from_pages(result.pages, "doc-test")
        self.assertGreater(len(chunks), 0)


class TestIndexPdfPipeline(unittest.TestCase):
    def setUp(self):
        init_db()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = self._tmpdir.name
        self.document_ids: list[str] = []

    def tearDown(self):
        for document_id in self.document_ids:
            delete_document(document_id)
        self._tmpdir.cleanup()

    def _track_document(self, filename: str) -> str:
        document_id = create_document(filename)
        self.document_ids.append(document_id)
        return document_id

    @patch("indexer.chromadb.PersistentClient")
    @patch("indexer.model")
    def test_indexing_failure_status(self, mock_model, mock_client):
        path = os.path.join(self.tmp, "empty-index.pdf")
        _write_blank_pdf(path)
        document_id = self._track_document("empty-index.pdf")

        index_pdf(path, document_id)

        record = get_document(document_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["index_error"], INDEX_FAILURE_NO_TEXT)
        mock_model.embed.assert_not_called()
        mock_client.assert_not_called()

    @patch("indexer.chromadb.PersistentClient")
    @patch("indexer.model")
    def test_indexing_success_after_extraction(self, mock_model, mock_client):
        path = os.path.join(self.tmp, "ready.pdf")
        long_page = ("Matter is made of particles. " * 25).strip()
        _write_text_pdf(path, [long_page, long_page])
        document_id = self._track_document("ready.pdf")

        mock_collection = MagicMock()
        mock_client.return_value.get_or_create_collection.return_value = mock_collection
        mock_model.embed.return_value = [[0.01] * 384]

        index_pdf(path, document_id)

        record = get_document(document_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["status"], "ready")
        self.assertIsNone(record["index_error"])
        self.assertGreater(record["total_chunks"], 0)
        mock_collection.add.assert_called()
        mock_model.embed.assert_called()

    def test_mark_document_index_failed_persists_message(self):
        document_id = self._track_document("failed-marker.pdf")
        message = "Example indexing failure."

        mark_document_index_failed(document_id, message)

        record = get_document(document_id)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["index_error"], message)


class TestExtractorUnits(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = self._tmpdir.name

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_pymupdf_reads_text_page_by_page(self):
        path = os.path.join(self.tmp, "unit-pymupdf.pdf")
        _write_text_pdf(path, ["Unit test page for PyMuPDF extraction."])

        pages, diagnostics = extract_pages_with_pymupdf(path)

        self.assertEqual(len(pages), 1)
        self.assertIn("PyMuPDF", pages[0]["text"])
        self.assertEqual(diagnostics[0]["engine"], PRIMARY_ENGINE)
        self.assertGreater(diagnostics[0]["chars"], 0)

    def test_pypdf_reads_text_page_by_page(self):
        path = os.path.join(self.tmp, "unit-pypdf.pdf")
        _write_text_pdf(path, ["Unit test page for pypdf extraction pipeline."])

        pages, diagnostics = extract_pages_with_pypdf(path)

        self.assertEqual(len(pages), 1)
        self.assertIn("pypdf", pages[0]["text"])
        self.assertEqual(diagnostics[0]["engine"], FALLBACK_ENGINE)


if __name__ == "__main__":
    unittest.main()
