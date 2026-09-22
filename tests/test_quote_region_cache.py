"""Tests for quote→region SQLite cache and sentence segments."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

import pymupdf as fitz

from database.db import init_db
from database.document_store import create_document, delete_document
from database.evidence_store import (
    get_quote_region_cache,
    quote_hash,
    replace_document_evidence,
)
from evidence_mapping import (
    SOURCE_NATIVE,
    Span,
    build_sentence_segments,
    map_quote_to_regions,
    split_sentences,
)
from pdf_extraction import PRIMARY_ENGINE
from quote_evidence import resolve_quote_evidence


def _write_text_pdf(path: str, text: str) -> None:
    doc = fitz.open()
    try:
        page = doc.new_page()
        page.insert_text((72, 72), text)
        doc.save(path)
    finally:
        doc.close()


class TestQuoteRegionCache(unittest.TestCase):
    def setUp(self):
        init_db()
        self.document_id = create_document("cache-test.pdf")
        self.chunk_id = f"{self.document_id}_0"
        replace_document_evidence(
            self.document_id,
            {
                "pages": [
                    {
                        "page_number": 1,
                        "width": 612.0,
                        "height": 792.0,
                        "source": SOURCE_NATIVE,
                        "engine": PRIMARY_ENGINE,
                        "span_count": 2,
                    }
                ],
                "chunks": [
                    {
                        "chunk_id": self.chunk_id,
                        "document_id": self.document_id,
                        "page_start": 1,
                        "page_end": 1,
                        "snippet": "Supervised learning uses labeled examples.",
                        "highlight_available": True,
                        "match_type": "normalized",
                        "source": SOURCE_NATIVE,
                        "text_engine": PRIMARY_ENGINE,
                        "layout_engine": PRIMARY_ENGINE,
                        "join_recovered": False,
                        "ranges": [{"page": 1, "char_start": 0, "char_end": 44, "match_type": "normalized"}],
                        "regions": [
                            {
                                "page": 1,
                                "x0": 10.0,
                                "y0": 20.0,
                                "x1": 80.0,
                                "y1": 36.0,
                                "coord_space": "pdf",
                            }
                        ],
                        "segments": [],
                    }
                ],
            },
        )

    def tearDown(self):
        delete_document(self.document_id)

    def test_quote_hash_is_stable(self):
        self.assertEqual(quote_hash("Hello World"), quote_hash("hello world"))

    @patch("quote_evidence._chunk_text_from_chroma", return_value="Supervised learning uses labeled examples.")
    @patch("quote_evidence.extract_page_layouts")
    def test_second_lookup_uses_cache(self, mock_layouts, _mock_text):
        mock_layouts.return_value = {}
        quote = "labeled examples"
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = os.path.join(tmp, "doc.pdf")
            _write_text_pdf(pdf_path, "Supervised learning uses labeled examples.")

            first = resolve_quote_evidence(
                document_id=self.document_id,
                chunk_id=self.chunk_id,
                quote=quote,
                pdf_path=pdf_path,
            )
            self.assertIsNotNone(first)
            cached = get_quote_region_cache(self.chunk_id, quote)
            self.assertIsNotNone(cached)

            second = resolve_quote_evidence(
                document_id=self.document_id,
                chunk_id=self.chunk_id,
                quote=quote,
                pdf_path=pdf_path,
            )
            self.assertEqual(first.get("quote_mapping_status"), second.get("quote_mapping_status"))
            # Cache path should not re-open PDF.
            self.assertEqual(mock_layouts.call_count, 1)


class TestSentenceSegments(unittest.TestCase):
    def test_split_sentences_finds_two(self):
        parts = split_sentences("First sentence here. Second sentence follows.")
        self.assertGreaterEqual(len(parts), 2)

    def test_map_quote_uses_precomputed_segment(self):
        chunk_text = "Alpha beta gamma. Delta epsilon zeta."
        segments = [
            {
                "index": 0,
                "text": "Alpha beta gamma.",
                "highlight_available": True,
                "match_type": "exact",
                "regions": [
                    {"page": 1, "x0": 1.0, "y0": 2.0, "x1": 10.0, "y1": 12.0, "coord_space": "pdf"}
                ],
            },
            {
                "index": 1,
                "text": "Delta epsilon zeta.",
                "highlight_available": True,
                "match_type": "exact",
                "regions": [
                    {"page": 1, "x0": 1.0, "y0": 20.0, "x1": 10.0, "y1": 30.0, "coord_space": "pdf"}
                ],
            },
        ]
        mapped = map_quote_to_regions(
            "Delta epsilon zeta.",
            chunk_text=chunk_text,
            layouts={},
            page_start=1,
            page_end=1,
            segments=segments,
        )
        self.assertTrue(mapped.get("quote_highlight_available"))
        self.assertEqual(mapped.get("segment_index"), 1)
        self.assertAlmostEqual(mapped["regions"][0]["y0"], 20.0)


if __name__ == "__main__":
    unittest.main()
