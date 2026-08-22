"""Edge-case tests for evidence fallbacks and answer polishing."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from answer_formatter import (
    limit_citation_markers,
    normalize_smart_quotes,
    polish_answer_text,
    remove_markdown_blockquote_dumps,
)
from claim_validator import annotate_source_evidence_availability, finalize_answer_citations
from database.document_store import create_document, delete_document
from database.evidence_store import document_evidence_summary, replace_document_evidence
from evidence_mapping import SOURCE_NATIVE, SOURCE_NONE
from quote_evidence import resolve_quote_evidence
from response_validator import is_valid_response


class TestAnswerFormatterEdgeCases(unittest.TestCase):
    def test_normalizes_smart_quotes_before_stripping(self):
        text = "Claim. \u201cThis is a very long smart quoted passage that should be removed from prose.\u201d Done."
        polished = polish_answer_text(text)
        self.assertNotIn("smart quoted passage", polished)
        self.assertIn("Done.", polished)

    def test_removes_markdown_blockquotes(self):
        text = "Overview here.\n> Long quoted block from the document that should not appear.\nMore text."
        self.assertNotIn("Long quoted block", remove_markdown_blockquote_dumps(text))

    def test_limits_excess_citation_markers(self):
        text = "A.[E1] B.[E2] C.[E3] D.[E4] E.[E5] F.[E6] G.[E7]"
        limited = limit_citation_markers(text, max_markers=5)
        self.assertIn("[E5]", limited)
        self.assertNotIn("[E6]", limited)
        self.assertNotIn("[E7]", limited)


class TestResponseValidatorEdgeCases(unittest.TestCase):
    def test_allows_grounded_not_found_response(self):
        self.assertTrue(
            is_valid_response(
                "I couldn't find that in the provided document."
            )
        )

    def test_blocks_empty_answer(self):
        self.assertFalse(is_valid_response("   "))

    def test_blocks_generic_refusal(self):
        self.assertFalse(is_valid_response("I don't know."))


class TestQuoteEvidenceFallback(unittest.TestCase):
    def setUp(self):
        self.document_id = create_document("edge-fallback.pdf")

    def tearDown(self):
        delete_document(self.document_id)

    @patch("quote_evidence._chunk_record_from_chroma")
    def test_missing_sidecar_returns_no_evidence_data(self, chunk_record):
        chunk_id = f"{self.document_id}_0"
        chunk_record.return_value = (
            "Supervised learning uses labeled examples.",
            {
                "document_id": self.document_id,
                "page_number": 3,
                "page_start": 3,
                "page_end": 3,
            },
        )
        payload = resolve_quote_evidence(
            document_id=self.document_id,
            chunk_id=chunk_id,
            quote="labeled examples",
            pdf_path=None,
        )
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["quote_mapping_status"], "no_evidence_data")
        self.assertFalse(payload["highlight_available"])
        self.assertEqual(payload["page_start"], 3)

    @patch("quote_evidence._chunk_record_from_chroma")
    def test_rejects_invalid_quote_on_fallback(self, chunk_record):
        chunk_id = f"{self.document_id}_0"
        chunk_record.return_value = (
            "Supervised learning uses labeled examples.",
            {"document_id": self.document_id, "page_number": 2},
        )
        payload = resolve_quote_evidence(
            document_id=self.document_id,
            chunk_id=chunk_id,
            quote='x0=12 y0=40 bbox injection',
            pdf_path=None,
        )
        assert payload is not None
        self.assertEqual(payload["quote_mapping_status"], "rejected")


class TestEvidenceSummary(unittest.TestCase):
    def setUp(self):
        self.document_id = create_document("edge-summary.pdf")

    def tearDown(self):
        delete_document(self.document_id)

    def test_document_evidence_summary_counts_highlights(self):
        replace_document_evidence(
            self.document_id,
            {
                "pages": [],
                "chunks": [
                    {
                        "chunk_id": f"{self.document_id}_0",
                        "document_id": self.document_id,
                        "page_start": 1,
                        "page_end": 1,
                        "snippet": "One",
                        "highlight_available": True,
                        "match_type": "exact",
                        "source": SOURCE_NATIVE,
                        "text_engine": "pymupdf",
                        "layout_engine": "pymupdf",
                        "join_recovered": False,
                        "ranges": [],
                        "regions": [],
                    },
                    {
                        "chunk_id": f"{self.document_id}_1",
                        "document_id": self.document_id,
                        "page_start": 2,
                        "page_end": 2,
                        "snippet": "Two",
                        "highlight_available": False,
                        "match_type": "failed",
                        "source": SOURCE_NONE,
                        "text_engine": "pymupdf",
                        "layout_engine": "pymupdf",
                        "join_recovered": False,
                        "ranges": [],
                        "regions": [],
                    },
                ],
            },
        )
        summary = document_evidence_summary(self.document_id)
        self.assertTrue(summary["has_evidence_data"])
        self.assertEqual(summary["chunk_evidence_count"], 2)
        self.assertEqual(summary["highlighted_chunk_count"], 1)


class TestAnnotateSourceAvailability(unittest.TestCase):
    def test_flags_missing_sidecar(self):
        sources = annotate_source_evidence_availability(
            [{"chunk_id": "missing-chunk", "evidence_id": "E1"}]
        )
        self.assertFalse(sources[0]["evidence_data_available"])
        self.assertFalse(sources[0]["highlight_available"])


if __name__ == "__main__":
    unittest.main()
