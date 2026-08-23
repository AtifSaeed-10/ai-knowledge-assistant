"""Phase 2B: chunk evidence lookup for PDF highlighting (no retrieval changes)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import app
from database.document_store import create_document, delete_document
from database.evidence_store import replace_document_evidence
from evidence_mapping import SOURCE_NATIVE, PageLayout, Span
from pdf_extraction import PRIMARY_ENGINE


def _chunk(
    document_id: str,
    chunk_id: str,
    *,
    page_start: int,
    page_end: int,
    snippet: str,
    highlight_available: bool,
    regions: list[dict],
) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "page_start": page_start,
        "page_end": page_end,
        "snippet": snippet,
        "highlight_available": highlight_available,
        "match_type": "normalized" if highlight_available else "failed",
        "source": SOURCE_NATIVE,
        "text_engine": PRIMARY_ENGINE,
        "layout_engine": PRIMARY_ENGINE,
        "join_recovered": False,
        "ranges": [],
        "regions": regions,
    }


class TestChunkEvidenceApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.document_id = create_document("phase2b-evidence.pdf")
        self.other_id = create_document("phase2b-other.pdf")

    def tearDown(self):
        delete_document(self.document_id)
        delete_document(self.other_id)

    def _put(self, chunks: list[dict]) -> None:
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
                        "span_count": 1,
                    }
                ],
                "chunks": chunks,
            },
        )

    def test_returns_page_and_regions_for_highlight(self):
        chunk_id = f"{self.document_id}_0"
        self._put(
            [
                _chunk(
                    self.document_id,
                    chunk_id,
                    page_start=4,
                    page_end=4,
                    snippet="Supervised learning uses labeled examples.",
                    highlight_available=True,
                    regions=[
                        {
                            "page": 4,
                            "x0": 10.0,
                            "y0": 20.0,
                            "x1": 80.0,
                            "y1": 36.0,
                            "coord_space": "pdf",
                        },
                        {
                            "page": 4,
                            "x0": 10.0,
                            "y0": 40.0,
                            "x1": 90.0,
                            "y1": 56.0,
                            "coord_space": "pdf",
                        },
                    ],
                )
            ]
        )

        response = self.client.get(
            f"/documents/{self.document_id}/chunks/{chunk_id}/evidence"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["chunk_id"], chunk_id)
        self.assertEqual(body["document_id"], self.document_id)
        self.assertEqual(body["page_start"], 4)
        self.assertEqual(body["page_end"], 4)
        self.assertTrue(body["highlight_available"])
        self.assertEqual(body["snippet"], "Supervised learning uses labeled examples.")
        self.assertEqual(len(body["regions"]), 2)
        self.assertEqual(body["regions"][0]["page"], 4)
        self.assertEqual(body["regions"][0]["coord_space"], "pdf")
        self.assertNotIn("match_type", body)
        self.assertFalse(body["quote_highlight_available"])
        self.assertEqual(body["quote_regions"], [])
        self.assertIsNone(body["quote"])
        self.assertEqual(body["quote_mapping_status"], "none")

    def test_multi_page_regions_are_returned_verbatim(self):
        chunk_id = f"{self.document_id}_1"
        self._put(
            [
                _chunk(
                    self.document_id,
                    chunk_id,
                    page_start=2,
                    page_end=3,
                    snippet="A claim that spans two pages.",
                    highlight_available=True,
                    regions=[
                        {
                            "page": 2,
                            "x0": 12.0,
                            "y0": 100.0,
                            "x1": 200.0,
                            "y1": 118.0,
                            "coord_space": "pdf",
                        },
                        {
                            "page": 3,
                            "x0": 12.0,
                            "y0": 40.0,
                            "x1": 180.0,
                            "y1": 58.0,
                            "coord_space": "pdf",
                        },
                    ],
                )
            ]
        )

        body = self.client.get(
            f"/documents/{self.document_id}/chunks/{chunk_id}/evidence"
        ).json()
        self.assertEqual(body["page_start"], 2)
        self.assertEqual(body["page_end"], 3)
        self.assertEqual([item["page"] for item in body["regions"]], [2, 3])

    def test_unavailable_highlight_returns_snippet_and_empty_regions(self):
        chunk_id = f"{self.document_id}_2"
        self._put(
            [
                _chunk(
                    self.document_id,
                    chunk_id,
                    page_start=7,
                    page_end=7,
                    snippet="OCR or unmapped passage.",
                    highlight_available=False,
                    regions=[],
                )
            ]
        )

        body = self.client.get(
            f"/documents/{self.document_id}/chunks/{chunk_id}/evidence"
        ).json()
        self.assertFalse(body["highlight_available"])
        self.assertEqual(body["page_start"], 7)
        self.assertEqual(body["snippet"], "OCR or unmapped passage.")
        self.assertEqual(body["regions"], [])
        self.assertEqual(body["quote_mapping_status"], "none")

    def test_unknown_chunk_or_document_is_404(self):
        missing = self.client.get(
            f"/documents/{self.document_id}/chunks/no-such-chunk/evidence"
        )
        self.assertEqual(missing.status_code, 404)

        unknown_doc = self.client.get(
            "/documents/not-a-real-id/chunks/anything/evidence"
        )
        self.assertEqual(unknown_doc.status_code, 404)

    def test_does_not_return_evidence_from_another_document(self):
        chunk_id = f"{self.document_id}_0"
        self._put(
            [
                _chunk(
                    self.document_id,
                    chunk_id,
                    page_start=1,
                    page_end=1,
                    snippet="Owned by document A.",
                    highlight_available=True,
                    regions=[
                        {
                            "page": 1,
                            "x0": 1.0,
                            "y0": 1.0,
                            "x1": 2.0,
                            "y1": 2.0,
                            "coord_space": "pdf",
                        }
                    ],
                )
            ]
        )

        response = self.client.get(
            f"/documents/{self.other_id}/chunks/{chunk_id}/evidence"
        )
        self.assertEqual(response.status_code, 404)


class TestQuoteEvidenceApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.document_id = create_document("quote-evidence.pdf")
        self.chunk_id = f"{self.document_id}_0"
        self.plain = (
            "Intro padding. Supervised learning uses labeled examples. "
            "Later, unsupervised learning finds hidden structure."
        )
        self.layouts = {
            1: PageLayout(
                page_number=1,
                width=612.0,
                height=792.0,
                plain=self.plain,
                spans=[
                    Span(
                        "Intro padding. ",
                        (10.0, 10.0, 80.0, 22.0),
                        (10.0, 10.0, 80.0, 22.0),
                    ),
                    Span(
                        "Supervised learning uses labeled examples.",
                        (10.0, 24.0, 220.0, 36.0),
                        (10.0, 24.0, 220.0, 36.0),
                    ),
                    Span(
                        " Later, ",
                        (10.0, 40.0, 60.0, 52.0),
                        (10.0, 40.0, 60.0, 52.0),
                    ),
                    Span(
                        "unsupervised learning finds hidden structure.",
                        (10.0, 56.0, 240.0, 68.0),
                        (10.0, 56.0, 240.0, 68.0),
                    ),
                ],
                source=SOURCE_NATIVE,
                engine=PRIMARY_ENGINE,
            )
        }
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
                        "span_count": 4,
                    }
                ],
                "chunks": [
                    _chunk(
                        self.document_id,
                        self.chunk_id,
                        page_start=1,
                        page_end=1,
                        snippet="Intro padding. Supervised learning uses labeled examples.",
                        highlight_available=True,
                        regions=[
                            {
                                "page": 1,
                                "x0": 10.0,
                                "y0": 10.0,
                                "x1": 80.0,
                                "y1": 22.0,
                                "coord_space": "pdf",
                            },
                            {
                                "page": 1,
                                "x0": 10.0,
                                "y0": 24.0,
                                "x1": 220.0,
                                "y1": 36.0,
                                "coord_space": "pdf",
                            },
                            {
                                "page": 1,
                                "x0": 10.0,
                                "y0": 40.0,
                                "x1": 60.0,
                                "y1": 52.0,
                                "coord_space": "pdf",
                            },
                            {
                                "page": 1,
                                "x0": 10.0,
                                "y0": 56.0,
                                "x1": 240.0,
                                "y1": 68.0,
                                "coord_space": "pdf",
                            },
                        ],
                    )
                ],
            },
        )

    def tearDown(self):
        delete_document(self.document_id)

    def _get(self, quote: str | None = None):
        params = {"quote": quote} if quote else None
        with patch(
            "quote_evidence._chunk_text_from_chroma",
            return_value=self.plain,
        ), patch(
            "quote_evidence.extract_page_layouts",
            return_value=self.layouts,
        ), patch(
            "backend.document_pdf_path",
            return_value="C:\\fake-quote-evidence.pdf",
        ):
            return self.client.get(
                f"/documents/{self.document_id}/chunks/{self.chunk_id}/evidence",
                params=params,
            )

    def test_valid_quote_returns_only_quote_regions(self):
        body = self._get("Supervised learning uses labeled examples.").json()
        self.assertEqual(body["quote"], "Supervised learning uses labeled examples.")
        self.assertTrue(body["quote_highlight_available"])
        self.assertEqual(len(body["quote_regions"]), 1)
        self.assertEqual(body["quote_regions"][0]["y0"], 24.0)
        self.assertEqual(len(body["regions"]), 4)
        self.assertTrue(body["highlight_available"])
        self.assertIn(body["quote_mapping_status"], {"exact", "normalized", "fuzzy_compact"})

    def test_quote_across_spans_returns_all_boxes(self):
        body = self._get("labeled examples. Later").json()
        self.assertTrue(body["quote_highlight_available"])
        self.assertEqual(len(body["quote_regions"]), 2)

    def test_missing_quote_keeps_chunk_fallback_without_guessing(self):
        body = self._get("this quote is not in the retrieved chunk").json()
        self.assertEqual(body["quote"], "this quote is not in the retrieved chunk")
        self.assertFalse(body["quote_highlight_available"])
        self.assertEqual(body["quote_regions"], [])
        self.assertEqual(body["quote_mapping_status"], "not_in_chunk")
        self.assertTrue(body["highlight_available"])
        self.assertEqual(len(body["regions"]), 4)

    def test_coordinates_in_quote_are_ignored(self):
        body = self._get("x0=12 y0=40 x1=80 y1=56").json()
        self.assertIsNone(body["quote"])
        self.assertFalse(body["quote_highlight_available"])
        self.assertEqual(body["quote_regions"], [])
        self.assertEqual(body["quote_mapping_status"], "rejected")
        self.assertEqual(len(body["regions"]), 4)

    def test_two_quotes_from_same_chunk_resolve_independently(self):
        first = self._get("Supervised learning uses labeled examples.").json()
        second = self._get("unsupervised learning finds hidden structure.").json()
        self.assertEqual(first["quote_regions"][0]["y0"], 24.0)
        self.assertEqual(second["quote_regions"][0]["y0"], 56.0)
        self.assertNotEqual(first["quote_regions"], second["quote_regions"])

    def test_no_quote_keeps_chunk_level_behavior(self):
        body = self._get().json()
        self.assertIsNone(body["quote"])
        self.assertFalse(body["quote_highlight_available"])
        self.assertEqual(body["quote_regions"], [])
        self.assertEqual(len(body["regions"]), 4)
        self.assertEqual(body["quote_mapping_status"], "none")


class TestVisualChunkEvidenceApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.document_id = create_document("visual-evidence.pdf")

    def tearDown(self):
        delete_document(self.document_id)

    def test_figure_caption_does_not_paint_chunk_wide_boxes(self):
        chunk_id = f"{self.document_id}_fig"
        replace_document_evidence(
            self.document_id,
            {
                "pages": [
                    {
                        "page_number": 6,
                        "width": 612.0,
                        "height": 792.0,
                        "source": SOURCE_NATIVE,
                        "engine": PRIMARY_ENGINE,
                        "span_count": 4,
                    }
                ],
                "chunks": [
                    _chunk(
                        self.document_id,
                        chunk_id,
                        page_start=6,
                        page_end=6,
                        snippet="Figure 2. Overview of the training pipeline.",
                        highlight_available=True,
                        regions=[
                            {
                                "page": 6,
                                "x0": 40.0,
                                "y0": 80.0,
                                "x1": 560.0,
                                "y1": 720.0,
                                "coord_space": "pdf",
                            }
                        ],
                    )
                ],
            },
        )
        body = self.client.get(
            f"/documents/{self.document_id}/chunks/{chunk_id}/evidence"
        ).json()
        self.assertEqual(body["content_type"], "figure_caption")
        self.assertFalse(body["highlight_available"])
        self.assertFalse(body["quote_highlight_available"])
        self.assertEqual(body["quote_regions"], [])
        self.assertEqual(body["page_start"], 6)


if __name__ == "__main__":
    unittest.main()
