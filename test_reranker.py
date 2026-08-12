"""Focused tests for RAG V2 Phase 3 cross-encoder reranking."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from reranker import (
    CrossEncoderReranker,
    RerankerUnavailableError,
    rerank_candidates,
    rrf_fallback_candidates,
    sigmoid_relevance,
)
from hybrid_retrieval import fuse_results, retrieve_candidates


class TestScoreHelpers(unittest.TestCase):
    def test_sigmoid_relevance_bounds(self):
        self.assertEqual(sigmoid_relevance(0.0), 50)
        self.assertGreater(sigmoid_relevance(5.0), 90)
        self.assertLess(sigmoid_relevance(-5.0), 10)


class TestRerankOrderingAndDedupe(unittest.TestCase):
    def test_dedupe_before_scoring_and_order_by_reranker(self):
        service = MagicMock()
        service.score.return_value = [1.0, 5.0]  # after dedupe: a, b

        candidates = [
            {
                "id": "a",
                "text": "alpha chunk",
                "metadata": {"document_id": "d1", "filename": "f.pdf", "page_number": 1},
                "dense_distance": 0.4,
                "bm25_score": 1.0,
                "rrf_score": 0.02,
                "sources": ["dense"],
            },
            {
                "id": "a",  # duplicate — must be ignored
                "text": "alpha chunk dup",
                "metadata": {"document_id": "d1", "filename": "f.pdf", "page_number": 1},
                "dense_distance": 0.9,
                "bm25_score": 9.0,
                "rrf_score": 0.01,
                "sources": ["bm25"],
            },
            {
                "id": "b",
                "text": "beta chunk",
                "metadata": {"document_id": "d1", "filename": "f.pdf", "page_number": 2},
                "dense_distance": 0.2,
                "bm25_score": 2.0,
                "rrf_score": 0.03,
                "sources": ["dense", "bm25"],
            },
        ]

        ranked = rerank_candidates(
            "what is beta",
            candidates,
            top_k=5,
            reranker_service=service,
        )

        self.assertEqual([c["id"] for c in ranked], ["b", "a"])
        service.score.assert_called_once()
        docs = service.score.call_args.args[1]
        self.assertEqual(docs, ["alpha chunk", "beta chunk"])

        # Score separation preserved
        top = ranked[0]
        self.assertEqual(top["reranker_score"], 5.0)
        self.assertEqual(top["dense_distance"], 0.2)
        self.assertEqual(top["bm25_score"], 2.0)
        self.assertEqual(top["rrf_score"], 0.03)
        self.assertNotEqual(top["reranker_score"], top["dense_distance"])
        self.assertEqual(top["relevance"], sigmoid_relevance(5.0))

    def test_min_score_filter(self):
        service = MagicMock()
        service.score.return_value = [-2.0, 3.0]
        candidates = [
            {
                "id": "low",
                "text": "no",
                "metadata": {},
                "dense_distance": 0.1,
                "bm25_score": None,
                "rrf_score": 0.05,
                "sources": ["dense"],
            },
            {
                "id": "high",
                "text": "yes",
                "metadata": {},
                "dense_distance": 0.5,
                "bm25_score": 1.0,
                "rrf_score": 0.01,
                "sources": ["bm25"],
            },
        ]
        ranked = rerank_candidates(
            "q",
            candidates,
            top_k=5,
            min_score=0.0,
            reranker_service=service,
        )
        self.assertEqual([c["id"] for c in ranked], ["high"])

    def test_top_k_cap(self):
        service = MagicMock()
        service.score.return_value = [3.0, 2.0, 1.0]
        candidates = [
            {
                "id": f"c{i}",
                "text": f"t{i}",
                "metadata": {},
                "dense_distance": 0.1,
                "bm25_score": 1.0,
                "rrf_score": 0.01 * i,
                "sources": ["dense"],
            }
            for i in range(3)
        ]
        ranked = rerank_candidates(
            "q",
            candidates,
            top_k=2,
            reranker_service=service,
        )
        self.assertEqual(len(ranked), 2)


class TestFallback(unittest.TestCase):
    def test_rrf_fallback_marks_none_reranker_score(self):
        candidates = [
            {
                "id": "x",
                "text": "one",
                "metadata": {},
                "dense_distance": 0.3,
                "bm25_score": 1.0,
                "rrf_score": 0.01,
                "sources": ["dense"],
            },
            {
                "id": "y",
                "text": "two",
                "metadata": {},
                "dense_distance": None,
                "bm25_score": 5.0,
                "rrf_score": 0.05,
                "sources": ["bm25"],
            },
        ]
        out = rrf_fallback_candidates(candidates, top_k=2, reason="load failed")
        self.assertEqual(out[0]["id"], "y")
        self.assertIsNone(out[0]["reranker_score"])
        self.assertTrue(out[0]["rerank_fallback"])
        self.assertEqual(out[0]["relevance"], 100)

    def test_ensure_loaded_failure_raises(self):
        service = CrossEncoderReranker(model_name="not-a-real/model")
        with patch(
            "fastembed.rerank.cross_encoder.TextCrossEncoder",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RerankerUnavailableError):
                service.ensure_loaded()
            self.assertIsNotNone(service.load_error)


class TestPipelineFallbackAndFilter(unittest.TestCase):
    def test_retrieve_candidates_fallback_and_score_fields(self):
        dense = [
            {
                "id": "c1",
                "text": "entropy definition",
                "metadata": {
                    "document_id": "docA",
                    "filename": "ml.pdf",
                    "page_number": 1,
                },
                "dense_distance": 0.25,
                "rank": 1,
            }
        ]
        bm25 = [
            {
                "id": "c2",
                "text": "football offside",
                "metadata": {
                    "document_id": "docB",
                    "filename": "fb.pdf",
                    "page_number": 2,
                },
                "bm25_score": 4.0,
                "rank": 1,
            }
        ]

        collection = MagicMock()
        embedding_model = MagicMock()

        with patch(
            "hybrid_retrieval.retrieve_dense",
            return_value=dense,
        ), patch(
            "hybrid_retrieval.retrieve_bm25",
            return_value=bm25,
        ), patch(
            "hybrid_retrieval.rerank_candidates",
            side_effect=RerankerUnavailableError("no model"),
        ):
            result = retrieve_candidates(
                "entropy",
                collection=collection,
                embedding_model=embedding_model,
                top_k=5,
            )

        self.assertTrue(result["rerank_fallback"])
        self.assertEqual(len(result["ids"]), 2)
        self.assertTrue(all(s is None for s in result["reranker_scores"]))
        # distances are dense-only (None for BM25-only)
        self.assertEqual(result["distances"][0], 0.25)
        self.assertIsNone(result["distances"][1])
        self.assertIn("relevances", result)
        self.assertIn("rrf_scores", result)
        self.assertIn("bm25_scores", result)

    def test_document_filter_still_applied_upstream(self):
        # fuse_results itself does not filter; retrieve_dense/bm25 do.
        # Ensure fused pool can be document-scoped inputs only.
        dense = [
            {
                "id": "a1",
                "text": "ml",
                "metadata": {"document_id": "docA", "filename": "a.pdf", "page_number": 1},
                "dense_distance": 0.2,
                "rank": 1,
            }
        ]
        bm25 = [
            {
                "id": "a2",
                "text": "ml2",
                "metadata": {"document_id": "docA", "filename": "a.pdf", "page_number": 2},
                "bm25_score": 3.0,
                "rank": 1,
            }
        ]
        fused = fuse_results(dense, bm25, top_k=10)
        self.assertTrue(all(c["metadata"]["document_id"] == "docA" for c in fused))

        service = MagicMock()
        service.score.return_value = [2.0, 1.0]
        ranked = rerank_candidates("q", fused, top_k=5, reranker_service=service)
        self.assertTrue(
            all(c["metadata"]["document_id"] == "docA" for c in ranked)
        )


if __name__ == "__main__":
    unittest.main()
