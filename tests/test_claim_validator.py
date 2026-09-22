"""Tests for claim validation and citation finalization."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from claim_validator import (
    finalize_answer_citations,
    repair_answer_markers,
    used_sources,
    validate_quote_against_chunk,
)
from citation_resolver import attach_quotes_to_sources


class TestValidateQuoteAgainstChunk(unittest.TestCase):
    def test_accepts_compact_match(self):
        chunk = "Supervised learning uses labeled examples for training."
        self.assertTrue(
            validate_quote_against_chunk("labeled examples for training", chunk)
        )

    def test_rejects_fabricated_quote(self):
        chunk = "Supervised learning uses labeled examples."
        self.assertFalse(
            validate_quote_against_chunk("this text is not in the chunk", chunk)
        )


class TestRepairAnswerMarkers(unittest.TestCase):
    def setUp(self):
        self.sources = [
            {
                "evidence_id": "E1",
                "chunk_id": "doc-a_0",
                "document_id": "doc-a",
            }
        ]

    @patch("claim_validator._chunk_text_for_source")
    def test_invalid_quote_downgrades_to_bare_marker(self, chunk_text):
        chunk_text.return_value = "Supervised learning uses labeled examples."
        answer = 'Claim.[E1:"fabricated wording not present"]'
        repaired = repair_answer_markers(answer, self.sources)
        self.assertEqual(repaired, "Claim.[E1]")

    @patch("claim_validator._chunk_text_for_source")
    def test_valid_quote_is_kept(self, chunk_text):
        chunk_text.return_value = "Supervised learning uses labeled examples."
        answer = 'Claim.[E1:"labeled examples"]'
        repaired = repair_answer_markers(answer, self.sources)
        self.assertEqual(repaired, 'Claim.[E1:"labeled examples"]')


class TestFinalizeAnswerCitations(unittest.TestCase):
    @patch("claim_validator._chunk_text_for_source")
    def test_strips_invalid_quotes_and_sets_mapping_status(
        self,
        chunk_text,
    ):
        chunk_text.return_value = "Supervised learning uses labeled examples."
        sources = [
            {
                "evidence_id": "E1",
                "chunk_id": "doc-a_0",
                "document_id": "doc-a",
                "filename": "ml.pdf",
                "page": 1,
                "relevance": 90,
            }
        ]
        answer = 'Uses labels.[E1:"fabricated quote"]'
        finalized_answer, enriched = finalize_answer_citations(
            answer,
            sources,
            resolve_regions=False,
        )
        self.assertEqual(finalized_answer, "Uses labels.[E1]")
        self.assertEqual(enriched[0]["quote_mapping_status"], "not_in_chunk")

    @patch("claim_validator.orchestrate_all_claims")
    @patch("claim_validator._chunk_text_for_source")
    def test_valid_quote_is_preserved(self, chunk_text, orchestrate):
        chunk_text.return_value = "Supervised learning uses labeled examples."
        sources = [
            {
                "evidence_id": "E1",
                "chunk_id": "doc-a_0",
                "document_id": "doc-a",
                "filename": "ml.pdf",
                "page": 1,
                "relevance": 90,
            }
        ]
        orchestrate.return_value = (
            [
                {
                    **sources[0],
                    "quote": "labeled examples",
                    "quotes": ["labeled examples"],
                    "quote_mapping_status": "exact",
                    "quote_highlight_available": True,
                    "quote_regions": [
                        {
                            "page": 1,
                            "x0": 1.0,
                            "y0": 2.0,
                            "x1": 3.0,
                            "y1": 4.0,
                            "coord_space": "pdf",
                        }
                    ],
                }
            ],
            {},
        )
        answer = 'Uses labels.[E1:"labeled examples"]'
        finalized_answer, enriched = finalize_answer_citations(
            answer,
            sources,
            resolve_regions=True,
        )
        self.assertIn('[E1:"labeled examples"]', finalized_answer)
        self.assertEqual(enriched[0]["quote"], "labeled examples")
        self.assertEqual(enriched[0]["quote_mapping_status"], "exact")


class TestUsedSources(unittest.TestCase):
    def test_keeps_only_cited_sources_in_order(self):
        sources = [
            {"evidence_id": "E1", "chunk_id": "a"},
            {"evidence_id": "E2", "chunk_id": "b"},
            {"evidence_id": "E3", "chunk_id": "c"},
        ]
        answer = 'First.[E2:"quote two"] Then.[E1:"quote one"]'
        kept = used_sources(sources, answer)
        self.assertEqual([item["evidence_id"] for item in kept], ["E2", "E1"])


class TestVisibleSources(unittest.TestCase):
    def test_refusal_attaches_nothing(self):
        from evidence_state import visible_sources

        sources = [
            {
                "evidence_id": "E1",
                "chunk_id": "h1",
                "snippet": "Notice must be given in writing.",
                "relevance": 22,
                "page": 7,
            }
        ]
        kept = visible_sources(
            sources,
            "I couldn't find that in the provided document.",
        )
        self.assertEqual(kept, [])

    def test_grounded_answer_without_markers_keeps_overlapping_page_only(self):
        from evidence_state import visible_sources

        sources = [
            {
                "evidence_id": "E1",
                "chunk_id": "h1",
                "snippet": "Either party may end the contract with thirty days written notice.",
                "relevance": 18,
                "page": 7,
                "evidence_state": "page_only",
            },
            {
                "evidence_id": "E2",
                "chunk_id": "h2",
                "snippet": "The office kitchen stocks tea and coffee.",
                "relevance": 12,
                "page": 40,
                "evidence_state": "page_only",
            },
        ]
        kept = visible_sources(
            sources,
            "The contract may be ended with thirty days written notice.",
        )
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["chunk_id"], "h1")
        self.assertEqual(kept[0]["evidence_state"], "page_only")
        self.assertEqual(kept[0]["page"], 7)


class TestAttachQuotesToSources(unittest.TestCase):
    def test_quotes_array_is_populated(self):
        sources = [{"evidence_id": "E1"}]
        answer = (
            'A.[E1:"supervised learning uses labeled examples"] '
            'B.[E1:"classification and regression"]'
        )
        attached = attach_quotes_to_sources(sources, answer)
        self.assertEqual(len(attached[0]["quotes"]), 2)
        self.assertEqual(attached[0]["quote"], "supervised learning uses labeled examples")


if __name__ == "__main__":
    unittest.main()
