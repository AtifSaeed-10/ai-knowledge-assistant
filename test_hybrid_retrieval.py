"""Deterministic tests for RAG V2 Phase 2 hybrid retrieval."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from bm25_index import BM25Index, corpus_fingerprint, tokenize
from hybrid_retrieval import fuse_results, retrieve_bm25, retrieve_dense


class TestTokenizeAndFingerprint(unittest.TestCase):
    def test_tokenize_deterministic(self):
        self.assertEqual(
            tokenize("Hello, BM25! Rank-Fusion 123"),
            ["hello", "bm25", "rank", "fusion", "123"],
        )

    def test_fingerprint_stable(self):
        a = corpus_fingerprint(["b", "a"])
        b = corpus_fingerprint(["a", "b"])
        self.assertEqual(a, b)
        self.assertNotEqual(a, corpus_fingerprint(["a", "c"]))


class TestRRFFusion(unittest.TestCase):
    def test_rrf_dedupes_by_chunk_id(self):
        dense = [
            {
                "id": "c1",
                "text": "alpha",
                "metadata": {"document_id": "d1", "filename": "a.pdf", "page_number": 1},
                "dense_distance": 0.2,
                "rank": 1,
            },
            {
                "id": "c2",
                "text": "beta",
                "metadata": {"document_id": "d1", "filename": "a.pdf", "page_number": 2},
                "dense_distance": 0.4,
                "rank": 2,
            },
        ]
        bm25 = [
            {
                "id": "c2",
                "text": "beta",
                "metadata": {"document_id": "d1", "filename": "a.pdf", "page_number": 2},
                "bm25_score": 5.0,
                "rank": 1,
            },
            {
                "id": "c3",
                "text": "gamma",
                "metadata": {"document_id": "d1", "filename": "a.pdf", "page_number": 3},
                "bm25_score": 3.0,
                "rank": 2,
            },
        ]
        fused = fuse_results(dense, bm25, rrf_k=60, top_k=5)
        ids = [item["id"] for item in fused]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {"c1", "c2", "c3"})
        # c2 appears in both lists → highest RRF
        self.assertEqual(fused[0]["id"], "c2")
        self.assertIn("dense", fused[0]["sources"])
        self.assertIn("bm25", fused[0]["sources"])

    def test_rrf_respects_top_k(self):
        dense = [
            {
                "id": f"d{i}",
                "text": f"t{i}",
                "metadata": {},
                "dense_distance": 0.1 * i,
                "rank": i,
            }
            for i in range(1, 6)
        ]
        bm25 = [
            {
                "id": f"b{i}",
                "text": f"u{i}",
                "metadata": {},
                "bm25_score": 10 - i,
                "rank": i,
            }
            for i in range(1, 6)
        ]
        fused = fuse_results(dense, bm25, rrf_k=60, top_k=3)
        self.assertEqual(len(fused), 3)

    def test_bm25_only_preserves_separated_scores(self):
        dense = []
        bm25 = [
            {
                "id": "only",
                "text": "exact term match",
                "metadata": {"page_number": 1},
                "bm25_score": 4.0,
                "rank": 1,
            }
        ]
        fused = fuse_results(dense, bm25, rrf_k=60, top_k=5)
        self.assertEqual(len(fused), 1)
        self.assertIsNone(fused[0]["dense_distance"])
        self.assertEqual(fused[0]["bm25_score"], 4.0)
        self.assertGreater(fused[0]["rrf_score"], 0)
        self.assertNotIn("reranker_score", fused[0])
        self.assertNotIn("distance", fused[0])


class TestBM25Index(unittest.TestCase):
    def test_search_and_document_filter(self):
        index = BM25Index()
        collection = MagicMock()
        collection.get.return_value = {
            "ids": ["a_0", "b_0", "a_1"],
            "documents": [
                "entropy information gain decision tree",
                "football offside rule advantage",
                "decision tree entropy cart",
            ],
            "metadatas": [
                {"document_id": "docA", "filename": "ml.pdf", "page_number": 1},
                {"document_id": "docB", "filename": "fb.pdf", "page_number": 2},
                {"document_id": "docA", "filename": "ml.pdf", "page_number": 3},
            ],
        }
        index.ensure_loaded(collection)
        self.assertEqual(index.size, 3)

        hits = index.search("entropy decision tree", k=5)
        self.assertGreaterEqual(len(hits), 1)
        self.assertTrue(all(h["bm25_score"] > 0 for h in hits))

        filtered = index.search(
            "entropy decision tree",
            k=5,
            document_ids=["docA"],
        )
        self.assertTrue(
            all(h["metadata"]["document_id"] == "docA" for h in filtered)
        )
        self.assertTrue(all(h["id"].startswith("a_") for h in filtered))

        # Fingerprint cache: second load without corpus change does not rebuild
        fp = index.fingerprint
        index.ensure_loaded(collection)
        self.assertEqual(index.fingerprint, fp)

        # Corpus change triggers rebuild
        collection.get.return_value = {
            "ids": ["a_0"],
            "documents": ["only one chunk now"],
            "metadatas": [{"document_id": "docA"}],
        }
        index.ensure_loaded(collection)
        self.assertEqual(index.size, 1)
        self.assertNotEqual(index.fingerprint, fp)


class TestRetrieveDenseMock(unittest.TestCase):
    def test_dense_applies_document_filter(self):
        collection = MagicMock()
        collection.count.return_value = 10
        collection.query.return_value = {
            "ids": [["x_1"]],
            "documents": [["text"]],
            "metadatas": [[{"document_id": "d1", "filename": "f.pdf", "page_number": 1}]],
            "distances": [[0.25]],
        }
        embedding_model = MagicMock()
        embedding_model.embed.return_value = [[0.1, 0.2, 0.3]]

        hits = retrieve_dense(
            "what is entropy",
            collection=collection,
            embedding_model=embedding_model,
            document_ids=["d1"],
            k=5,
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["dense_distance"], 0.25)
        kwargs = collection.query.call_args.kwargs
        self.assertEqual(kwargs["where"], {"document_id": "d1"})
        self.assertEqual(kwargs["n_results"], 5)


if __name__ == "__main__":
    unittest.main()
