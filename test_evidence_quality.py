"""Regression tests for evidence quality and citation filtering in rag.py."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from rag import ask_question
from reranker import rerank_candidates


class TestCitationFiltering(unittest.TestCase):
    def test_citations_skip_below_citation_threshold(self):
        retrieval = {
            "chunks": [
                "Strong supervised learning evidence.",
                "Marginal but usable context.",
            ],
            "distances": [0.2, 0.5],
            "metadata": [
                {
                    "document_id": "docA",
                    "filename": "ml.pdf",
                    "page_number": 10,
                },
                {
                    "document_id": "docA",
                    "filename": "ml.pdf",
                    "page_number": 20,
                },
            ],
            "ids": ["docA_1", "docA_2"],
            "relevances": [85, 28],
            "reranker_scores": [3.0, -1.0],
            "rerank_fallback": False,
        }

        with patch(
            "rag.retrieve_candidates",
            return_value=retrieval,
        ), patch(
            "rag.generate_response",
            return_value="Supervised learning uses labeled data.",
        ):
            result = ask_question(
                "What is supervised learning?",
                None,
                ["docA"],
                generate=True,
            )

        self.assertIn("[E1]", result["prompt"])
        self.assertIn("[E2]", result["prompt"])
        self.assertIn("Strong supervised learning evidence.", result["prompt"])
        self.assertIn("Marginal but usable context.", result["prompt"])
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["chunk_id"], "docA_1")
        self.assertEqual(result["sources"][0]["evidence_state"], "page_only")
        self.assertGreaterEqual(result["sources"][0]["relevance"], 30)

    def test_unanswerable_returns_no_weak_citations(self):
        retrieval = {
            "chunks": [],
            "distances": [],
            "metadata": [],
            "ids": [],
            "relevances": [],
            "reranker_scores": [],
            "rerank_fallback": False,
        }

        with patch(
            "rag.retrieve_candidates",
            return_value=retrieval,
        ):
            result = ask_question(
                "What is the capital of France?",
                None,
                ["docA"],
                generate=True,
            )

        self.assertEqual(result["sources"], [])
        self.assertIn(
            "No relevant information",
            result["answer"],
        )

    def test_weak_pipeline_evidence_reaches_llm_recall_pool_not_citations(self):
        service = MagicMock()
        service.score.return_value = [-7.0, -8.0]
        candidates = [
            {
                "id": "fb_1",
                "text": "irrelevant football offside rule text",
                "metadata": {
                    "document_id": "docB",
                    "filename": "fb.pdf",
                    "page_number": 3,
                },
                "dense_distance": 1.1,
                "bm25_score": 2.0,
                "rrf_score": 0.03,
                "sources": ["bm25"],
            },
            {
                "id": "fb_2",
                "text": "another unrelated sports paragraph",
                "metadata": {
                    "document_id": "docB",
                    "filename": "fb.pdf",
                    "page_number": 8,
                },
                "dense_distance": None,
                "bm25_score": 1.5,
                "rrf_score": 0.02,
                "sources": ["bm25"],
            },
        ]

        with patch(
            "hybrid_retrieval.rerank_candidates",
            side_effect=lambda query, fused, **kwargs: rerank_candidates(
                query,
                fused,
                reranker_service=service,
                **kwargs,
            ),
        ), patch(
            "hybrid_retrieval.retrieve_dense",
            return_value=[
                {
                    "id": c["id"],
                    "text": c["text"],
                    "metadata": c["metadata"],
                    "dense_distance": c["dense_distance"],
                    "rank": i + 1,
                }
                for i, c in enumerate(candidates)
            ],
        ), patch(
            "hybrid_retrieval.retrieve_bm25",
            return_value=[
                {
                    "id": c["id"],
                    "text": c["text"],
                    "metadata": c["metadata"],
                    "bm25_score": c["bm25_score"],
                    "rank": i + 1,
                }
                for i, c in enumerate(candidates)
            ],
        ):
            from hybrid_retrieval import retrieve_candidates as hybrid_retrieve

            result = hybrid_retrieve(
                "What is the capital of France?",
                collection=MagicMock(),
                embedding_model=MagicMock(),
                top_k=5,
            )

        self.assertGreaterEqual(len(result["chunks"]), 1)
        self.assertGreaterEqual(len(result["ids"]), 1)
        self.assertEqual(result["fused_count"], 2)
        self.assertTrue(result["recall_fallback"])
        self.assertTrue(all(not flag for flag in result["citation_eligible"]))
        self.assertTrue(
            all(int(rel or 0) < 30 for rel in result["relevances"])
        )

    def test_recall_fallback_grounded_answer_keeps_page_only_evidence(self):
        retrieval = {
            "chunks": [
                "Nanking is also spelled Nanjing in later scholarship."
            ],
            "distances": [0.8],
            "metadata": [
                {
                    "document_id": "ww2",
                    "filename": "ww2_history.pdf",
                    "page_number": 19,
                }
            ],
            "ids": ["ww2_21"],
            "relevances": [4],
            "reranker_scores": [-6.2],
            "citation_eligible": [False],
            "recall_fallbacks": [True],
            "recall_fallback": True,
            "fused_count": 20,
            "rerank_fallback": False,
        }

        with patch(
            "rag.retrieve_candidates",
            return_value=retrieval,
        ), patch(
            "rag.generate_response",
            return_value="The text also uses the spelling Nanjing.",
        ):
            result = ask_question(
                "Does the book mention the spelling Nanjing?",
                None,
                ["ww2"],
                generate=True,
            )

        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["evidence_state"], "page_only")
        self.assertEqual(result["sources"][0]["evidence_id"], "E1")
        self.assertEqual(result["sources"][0]["page"], 19)
        self.assertIn("[E1]", result["prompt"])
        self.assertIn("Nanjing", result["prompt"])
        self.assertNotIn("No relevant information", result["answer"])


if __name__ == "__main__":
    unittest.main()
