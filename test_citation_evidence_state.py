"""Item 8: E# identity is independent of citeable vs page_only evidence state."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from conversation_query import analyze_turn
from evidence_state import (
    STATE_CITEABLE,
    STATE_PAGE_ONLY,
    looks_like_evidence_refusal,
    visible_sources,
)
from rag import _build_citation_sources, ask_question


NOTICE_CHUNK = (
    "Either party may terminate the agreement by giving thirty days written "
    "notice to the other party's registered office."
)
HOLIDAY_CHUNK = (
    "Remote work requests are reviewed by the facilities coordinator each March."
)
CATERING_CHUNK = (
    "The office kitchen is stocked with tea, coffee, and biscuits for staff."
)


def _handbook_retrieval(*, relevances):
    return {
        "chunks": [NOTICE_CHUNK, HOLIDAY_CHUNK],
        "distances": [0.2, 0.3],
        "metadata": [
            {"document_id": "handbook", "filename": "staff_handbook.pdf", "page_number": 12},
            {"document_id": "handbook", "filename": "staff_handbook.pdf", "page_number": 28},
        ],
        "ids": ["handbook_12", "handbook_28"],
        "relevances": list(relevances),
        "reranker_scores": [1.0, 0.4],
        "citation_eligible": [rel >= 30 for rel in relevances],
        "rerank_fallback": False,
    }


class TestEvidenceStateAssignment(unittest.TestCase):
    def test_low_relevance_chunk_still_gets_evidence_id_as_page_only(self):
        sources, evidence_ids = _build_citation_sources(
            [NOTICE_CHUNK, HOLIDAY_CHUNK],
            ["handbook_12", "handbook_28"],
            [
                {
                    "document_id": "handbook",
                    "filename": "staff_handbook.pdf",
                    "page_number": 12,
                },
                {
                    "document_id": "handbook",
                    "filename": "staff_handbook.pdf",
                    "page_number": 28,
                },
            ],
            [88, 18],
            "How much notice is required to end the agreement?",
            analyze_turn("How much notice is required to end the agreement?", None),
            [True, False],
        )
        self.assertEqual([src["evidence_id"] for src in sources], ["E1", "E2"])
        self.assertEqual(evidence_ids, ["E1", "E2"])
        self.assertEqual(sources[0]["evidence_state"], STATE_CITEABLE)
        self.assertEqual(sources[1]["evidence_state"], STATE_PAGE_ONLY)
        self.assertTrue(sources[0]["citation_eligible"])
        self.assertFalse(sources[1]["citation_eligible"])

    def test_listing_allowlist_does_not_drop_ids(self):
        parent = (
            "Machine learning can be classified into supervised, unsupervised, "
            "and reinforcement learning."
        )
        child = "Decision trees split nodes using information gain."
        sources, evidence_ids = _build_citation_sources(
            [parent, child],
            ["ml_5", "ml_6"],
            [
                {"document_id": "doc-a", "filename": "ml.pdf", "page_number": 5},
                {"document_id": "doc-a", "filename": "ml.pdf", "page_number": 6},
            ],
            [91, 70],
            "What are the types of supervised learning?",
            analyze_turn("What are the types of supervised learning?", None),
            [True, True],
        )
        self.assertEqual(evidence_ids, ["E1", "E2"])
        self.assertTrue(all(src["evidence_id"] for src in sources))
        self.assertTrue(all(src["evidence_state"] == STATE_PAGE_ONLY for src in sources))


class TestVisibleSourcePolicy(unittest.TestCase):
    def test_refusal_keeps_ui_empty(self):
        self.assertTrue(
            looks_like_evidence_refusal(
                "I couldn't find that in the provided document."
            )
        )
        self.assertTrue(
            looks_like_evidence_refusal(
                "I couldn\u2019t find that in the provided document."
            )
        )
        sources = [
            {
                "evidence_id": "E1",
                "chunk_id": "handbook_12",
                "snippet": NOTICE_CHUNK,
                "relevance": 22,
                "page": 12,
            }
        ]
        self.assertEqual(
            visible_sources(sources, "I couldn't find that in the provided document."),
            [],
        )

    def test_grounded_answer_without_markers_keeps_overlapping_page(self):
        sources = [
            {
                "evidence_id": "E1",
                "chunk_id": "handbook_12",
                "snippet": NOTICE_CHUNK,
                "relevance": 22,
                "page": 12,
                "evidence_state": STATE_PAGE_ONLY,
            },
            {
                "evidence_id": "E2",
                "chunk_id": "handbook_40",
                "snippet": CATERING_CHUNK,
                "relevance": 11,
                "page": 40,
                "evidence_state": STATE_PAGE_ONLY,
            },
        ]
        kept = visible_sources(
            sources,
            "The agreement can be ended with thirty days written notice.",
        )
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["chunk_id"], "handbook_12")
        self.assertEqual(kept[0]["evidence_state"], STATE_PAGE_ONLY)
        self.assertEqual(kept[0]["page"], 12)

    def test_markers_still_win(self):
        sources = [
            {
                "evidence_id": "E1",
                "chunk_id": "handbook_12",
                "snippet": NOTICE_CHUNK,
                "relevance": 80,
                "page": 12,
                "evidence_state": STATE_CITEABLE,
            },
            {
                "evidence_id": "E2",
                "chunk_id": "handbook_28",
                "snippet": HOLIDAY_CHUNK,
                "relevance": 70,
                "page": 28,
                "evidence_state": STATE_CITEABLE,
            },
        ]
        kept = visible_sources(sources, "Holiday entitlement is twenty days.[E2]")
        self.assertEqual([src["evidence_id"] for src in kept], ["E2"])


class TestAskQuestionEvidenceState(unittest.TestCase):
    def test_grounded_low_relevance_notice_clause_is_visible(self):
        retrieval = _handbook_retrieval(relevances=[22, 8])
        with patch("rag.retrieve_candidates", return_value=retrieval), patch(
            "rag.generate_response",
            return_value="The agreement can be ended with thirty days written notice.",
        ):
            result = ask_question(
                "How much notice is required to end the agreement?",
                None,
                ["handbook"],
                generate=True,
            )
        self.assertIn("[E1]", result["prompt"])
        self.assertIn("[E2]", result["prompt"])
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["chunk_id"], "handbook_12")
        self.assertEqual(result["sources"][0]["evidence_state"], STATE_PAGE_ONLY)
        self.assertEqual(result["sources"][0]["page"], 12)

    def test_refusal_does_not_surface_off_topic_pages(self):
        retrieval = _handbook_retrieval(relevances=[12, 9])
        with patch("rag.retrieve_candidates", return_value=retrieval), patch(
            "rag.generate_response",
            return_value="I couldn't find that in the provided document.",
        ):
            result = ask_question(
                "Who won the World Cup?",
                None,
                ["handbook"],
                generate=True,
            )
        self.assertEqual(result["sources"], [])

    def test_empty_retrieval_stays_empty(self):
        retrieval = {
            "chunks": [],
            "distances": [],
            "metadata": [],
            "ids": [],
            "relevances": [],
            "reranker_scores": [],
            "rerank_fallback": False,
        }
        with patch("rag.retrieve_candidates", return_value=retrieval):
            result = ask_question(
                "Who won the World Cup?",
                None,
                ["handbook"],
                generate=True,
            )
        self.assertEqual(result["sources"], [])


if __name__ == "__main__":
    unittest.main()
