"""Focused tests for RAG V2 Phase 3 cross-encoder reranking."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from config import (
    RERANKER_MODEL_BGE,
    RERANKER_MODEL_MINILM,
    resolve_reranker_model,
)
from reranker import (
    CrossEncoderReranker,
    RerankerUnavailableError,
    dedupe_exact_text,
    diversify_by_page,
    filter_min_relevance,
    has_dual_retrieval_support,
    rerank_candidates,
    rrf_fallback_candidates,
    select_evidence,
    sigmoid_relevance,
    suppress_near_duplicates,
    text_overlap_ratio,
    truncate_for_rerank,
)
from hybrid_retrieval import fuse_results, retrieve_candidates


class TestRerankerModelConfig(unittest.TestCase):
    def test_resolve_aliases(self):
        self.assertEqual(resolve_reranker_model("bge"), RERANKER_MODEL_BGE)
        self.assertEqual(resolve_reranker_model("minilm"), RERANKER_MODEL_MINILM)
        self.assertEqual(
            resolve_reranker_model(RERANKER_MODEL_MINILM),
            RERANKER_MODEL_MINILM,
        )


class TestScoreHelpers(unittest.TestCase):
    def test_sigmoid_relevance_bounds(self):
        self.assertEqual(sigmoid_relevance(0.0), 50)
        self.assertGreater(sigmoid_relevance(5.0), 90)
        self.assertLess(sigmoid_relevance(-5.0), 10)

    def test_truncate_head_tail(self):
        text = "A" * 100 + "MID" + "B" * 100
        out = truncate_for_rerank(text, max_chars=40)
        self.assertLessEqual(len(out), 40)
        self.assertTrue(out.startswith("A"))
        self.assertTrue(out.endswith("B"))
        self.assertIn("...", out)
        # Full text unchanged when under limit
        self.assertEqual(truncate_for_rerank("short", max_chars=40), "short")

    def test_exact_text_dedupe_prefers_higher_rrf(self):
        cands = [
            {
                "id": "z",
                "text": "same",
                "rrf_score": 0.01,
                "metadata": {"page_number": 1},
            },
            {
                "id": "a",
                "text": "same",
                "rrf_score": 0.05,
                "metadata": {"page_number": 2},
            },
            {
                "id": "b",
                "text": "other",
                "rrf_score": 0.02,
                "metadata": {"page_number": 3},
            },
        ]
        unique, removed = dedupe_exact_text(cands)
        self.assertEqual(removed, 1)
        self.assertEqual(len(unique), 2)
        self.assertEqual(unique[0]["id"], "a")
        self.assertEqual(unique[0]["metadata"]["page_number"], 2)


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

        # Score separation preserved; full text kept for context
        top = ranked[0]
        self.assertEqual(top["reranker_score"], 5.0)
        self.assertEqual(top["text"], "beta chunk")
        self.assertEqual(top["dense_distance"], 0.2)
        self.assertEqual(top["bm25_score"], 2.0)
        self.assertEqual(top["rrf_score"], 0.03)
        self.assertNotEqual(top["reranker_score"], top["dense_distance"])
        self.assertEqual(top["relevance"], sigmoid_relevance(5.0))

    def test_exact_duplicate_text_scored_once(self):
        service = MagicMock()
        service.score.return_value = [4.0]
        shared = "identical entropy paragraph " * 20
        candidates = [
            {
                "id": "copy_b",
                "text": shared,
                "metadata": {"document_id": "d2", "filename": "f.pdf", "page_number": 30},
                "dense_distance": 0.3,
                "bm25_score": 2.0,
                "rrf_score": 0.02,
                "sources": ["dense"],
            },
            {
                "id": "copy_a",
                "text": shared,
                "metadata": {"document_id": "d1", "filename": "f.pdf", "page_number": 30},
                "dense_distance": 0.25,
                "bm25_score": 3.0,
                "rrf_score": 0.04,
                "sources": ["bm25", "dense"],
            },
        ]
        stats: dict = {}
        ranked = rerank_candidates(
            "entropy",
            candidates,
            top_k=5,
            reranker_service=service,
            stats_out=stats,
        )
        self.assertEqual(stats["deduped_count"], 1)
        self.assertEqual(stats["unique_count"], 1)
        self.assertEqual(len(service.score.call_args.args[1]), 1)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["id"], "copy_a")
        self.assertEqual(ranked[0]["text"], shared)

    def test_scores_truncated_text_keeps_full_chunk(self):
        service = MagicMock()
        service.score.return_value = [2.5]
        full = "HEAD" + ("x" * 500) + "TAIL"
        ranked = rerank_candidates(
            "q",
            [
                {
                    "id": "c1",
                    "text": full,
                    "metadata": {"document_id": "d1", "filename": "f.pdf", "page_number": 1},
                    "dense_distance": 0.2,
                    "bm25_score": 1.0,
                    "rrf_score": 0.02,
                    "sources": ["dense"],
                }
            ],
            top_k=1,
            max_chars=40,
            reranker_service=service,
        )
        scored_doc = service.score.call_args.args[1][0]
        self.assertLessEqual(len(scored_doc), 40)
        self.assertEqual(ranked[0]["text"], full)

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
                "metadata": {"page_number": i + 1},
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


class TestEvidenceSelection(unittest.TestCase):
    def test_diversify_by_page_keeps_one_slot_per_page(self):
        candidates = [
            {
                "id": "a1",
                "text": "first on page 10",
                "metadata": {
                    "document_id": "docA",
                    "filename": "ml.pdf",
                    "page_number": 10,
                },
                "reranker_score": 5.0,
                "relevance": 99,
                "rrf_score": 0.02,
            },
            {
                "id": "a2",
                "text": "second on page 10",
                "metadata": {
                    "document_id": "docA",
                    "filename": "ml.pdf",
                    "page_number": 10,
                },
                "reranker_score": 4.0,
                "relevance": 98,
                "rrf_score": 0.03,
            },
            {
                "id": "b1",
                "text": "page 20 chunk",
                "metadata": {
                    "document_id": "docA",
                    "filename": "ml.pdf",
                    "page_number": 20,
                },
                "reranker_score": 3.0,
                "relevance": 95,
                "rrf_score": 0.01,
            },
        ]
        picked = diversify_by_page(candidates, top_k=5)
        self.assertEqual([c["id"] for c in picked], ["a1", "b1"])

    def test_filter_min_relevance_drops_weak_evidence(self):
        candidates = [
            {"id": "weak", "relevance": 5, "metadata": {"page_number": 1}},
            {"id": "ok", "relevance": 40, "metadata": {"page_number": 2}},
        ]
        kept = filter_min_relevance(candidates, 25)
        self.assertEqual([c["id"] for c in kept], ["ok"])

    def test_select_evidence_filters_then_diversifies(self):
        service = MagicMock()
        service.score.return_value = [4.0, 3.5, -6.0, 2.0]
        candidates = [
            {
                "id": "p10_a",
                "text": "supervised learning definition",
                "metadata": {
                    "document_id": "docA",
                    "filename": "ml.pdf",
                    "page_number": 10,
                },
                "dense_distance": 0.2,
                "bm25_score": 1.0,
                "rrf_score": 0.04,
                "sources": ["dense"],
            },
            {
                "id": "p10_b",
                "text": "more supervised learning on same page",
                "metadata": {
                    "document_id": "docA",
                    "filename": "ml.pdf",
                    "page_number": 10,
                },
                "dense_distance": 0.3,
                "bm25_score": 1.0,
                "rrf_score": 0.03,
                "sources": ["bm25"],
            },
            {
                "id": "p30_noise",
                "text": "irrelevant football",
                "metadata": {
                    "document_id": "docB",
                    "filename": "fb.pdf",
                    "page_number": 30,
                },
                "dense_distance": 1.0,
                "bm25_score": 2.0,
                "rrf_score": 0.02,
                "sources": ["bm25"],
            },
            {
                "id": "p20_good",
                "text": "decision tree entropy",
                "metadata": {
                    "document_id": "docA",
                    "filename": "ml.pdf",
                    "page_number": 20,
                },
                "dense_distance": 0.4,
                "bm25_score": 1.5,
                "rrf_score": 0.01,
                "sources": ["dense"],
            },
        ]
        ranked = rerank_candidates(
            "what is supervised learning",
            candidates,
            top_k=3,
            reranker_service=service,
        )
        self.assertEqual([c["id"] for c in ranked], ["p10_a", "p20_good"])
        self.assertTrue(all(c["relevance"] >= 25 for c in ranked))

    def test_near_duplicate_suppression_prefers_higher_score(self):
        shared = (
            "Supervised learning uses labeled data to train predictive models. "
            "The algorithm learns from input-output pairs."
        )
        near_dup = shared + " Minor trailing overlap padding."
        candidates = [
            {
                "id": "strong",
                "text": near_dup,
                "metadata": {
                    "document_id": "docA",
                    "filename": "ml.pdf",
                    "page_number": 11,
                },
                "reranker_score": 4.5,
                "relevance": 98,
                "rrf_score": 0.02,
            },
            {
                "id": "weak_dup",
                "text": shared,
                "metadata": {
                    "document_id": "docA",
                    "filename": "ml.pdf",
                    "page_number": 12,
                },
                "reranker_score": 3.0,
                "relevance": 95,
                "rrf_score": 0.03,
            },
        ]
        kept = suppress_near_duplicates(candidates)
        self.assertEqual([c["id"] for c in kept], ["strong"])
        self.assertEqual(kept[0]["text"], near_dup)

    def test_different_topics_not_suppressed_as_near_duplicates(self):
        candidates = [
            {
                "id": "sup",
                "text": "Supervised learning uses labeled training examples.",
                "metadata": {
                    "document_id": "docA",
                    "page_number": 10,
                },
                "reranker_score": 4.0,
                "relevance": 95,
            },
            {
                "id": "unsup",
                "text": "Unsupervised learning finds hidden patterns without labels.",
                "metadata": {
                    "document_id": "docA",
                    "page_number": 20,
                },
                "reranker_score": 3.5,
                "relevance": 92,
            },
        ]
        kept = suppress_near_duplicates(candidates)
        self.assertEqual([c["id"] for c in kept], ["sup", "unsup"])

    def test_adjacent_chunk_overlap_stays_below_near_dup_threshold(self):
        tail = "entropy measures uncertainty in decision trees. "
        head = "information gain splits nodes effectively. "
        chunk_a = head + ("context " * 140) + tail
        chunk_b = tail + ("more context " * 130) + head
        ratio = text_overlap_ratio(chunk_a, chunk_b)
        self.assertLess(ratio, 0.72)
        candidates = [
            {
                "id": "chunk_a",
                "text": chunk_a,
                "metadata": {"document_id": "docA", "page_number": 5},
                "reranker_score": 3.0,
                "relevance": 90,
            },
            {
                "id": "chunk_b",
                "text": chunk_b,
                "metadata": {"document_id": "docA", "page_number": 6},
                "reranker_score": 2.5,
                "relevance": 88,
            },
        ]
        kept = suppress_near_duplicates(candidates)
        self.assertEqual(len(kept), 2)

    def test_select_evidence_preserves_full_chunk_text(self):
        service = MagicMock()
        full_text = "HEAD" + ("x" * 500) + "TAIL"
        service.score.return_value = [3.0, 2.5]
        candidates = [
            {
                "id": "c1",
                "text": full_text,
                "metadata": {
                    "document_id": "docA",
                    "filename": "ml.pdf",
                    "page_number": 1,
                },
                "dense_distance": 0.2,
                "bm25_score": 1.0,
                "rrf_score": 0.04,
                "sources": ["dense"],
            },
            {
                "id": "c2",
                "text": "Unrelated unsupervised learning overview.",
                "metadata": {
                    "document_id": "docA",
                    "filename": "ml.pdf",
                    "page_number": 2,
                },
                "dense_distance": 0.3,
                "bm25_score": 1.0,
                "rrf_score": 0.03,
                "sources": ["bm25"],
            },
        ]
        ranked = rerank_candidates(
            "entropy",
            candidates,
            top_k=2,
            max_chars=40,
            reranker_service=service,
        )
        self.assertEqual(ranked[0]["text"], full_text)
        scored_doc = service.score.call_args.args[1][0]
        self.assertLessEqual(len(scored_doc), 40)

    def test_unanswerable_pipeline_returns_no_evidence(self):
        service = MagicMock()
        service.score.return_value = [-7.0, -8.5, -6.0]
        candidates = [
            {
                "id": f"noise_{i}",
                "text": f"irrelevant football noise paragraph {i}",
                "metadata": {
                    "document_id": "docB",
                    "filename": "fb.pdf",
                    "page_number": i + 1,
                },
                "dense_distance": 1.2,
                "bm25_score": 2.0,
                "rrf_score": 0.02,
                "sources": ["bm25"],
            }
            for i in range(3)
        ]
        ranked = rerank_candidates(
            "What is the capital of France?",
            candidates,
            top_k=5,
            reranker_service=service,
        )
        self.assertEqual(ranked, [])


class TestDualSourceFallback(unittest.TestCase):
    def _entropy_why_pool(self):
        return [
            {
                "id": "entropy_93",
                "text": (
                    "lower values imply less uncertainty while higher values "
                    "imply high uncertainty in entropy."
                ),
                "metadata": {
                    "document_id": "docA",
                    "filename": "ml.pdf",
                    "page_number": 30,
                },
                "dense_distance": 0.57,
                "bm25_score": 18.1,
                "rrf_score": 0.0293,
                "sources": ["dense", "bm25"],
            },
            {
                "id": "noise_34",
                "text": "particular kind of phone unrelated marketing text",
                "metadata": {
                    "document_id": "docB",
                    "filename": "other.pdf",
                    "page_number": 34,
                },
                "dense_distance": None,
                "bm25_score": 15.0,
                "rrf_score": 0.0156,
                "sources": ["bm25"],
            },
        ]

    def test_entropy_why_query_admits_dual_source_minilm_false_negative(self):
        service = MagicMock()
        service.score.return_value = [-4.4518, -5.5941]
        ranked = rerank_candidates(
            "Why is lower entropy better when choosing a split?",
            self._entropy_why_pool(),
            top_k=5,
            reranker_service=service,
        )
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["id"], "entropy_93")
        self.assertIn("less uncertainty", ranked[0]["text"])

    def test_france_query_remains_empty_without_dual_source(self):
        service = MagicMock()
        service.score.return_value = [-10.9996, -11.0083]
        candidates = [
            {
                "id": "fr_1",
                "text": "football geography noise",
                "metadata": {"document_id": "fb", "page_number": 47},
                "dense_distance": 0.9,
                "bm25_score": None,
                "rrf_score": 0.02,
                "sources": ["dense"],
            },
            {
                "id": "fr_2",
                "text": "more unrelated text",
                "metadata": {"document_id": "fb", "page_number": 40},
                "dense_distance": 0.91,
                "bm25_score": None,
                "rrf_score": 0.01,
                "sources": ["dense"],
            },
        ]
        ranked = rerank_candidates(
            "What is the capital of France?",
            candidates,
            top_k=5,
            reranker_service=service,
        )
        self.assertEqual(ranked, [])

    def test_world_cup_query_remains_empty(self):
        service = MagicMock()
        service.score.return_value = [-5.9783, -7.5695]
        candidates = [
            {
                "id": "wc_1",
                "text": "world cup adjacent football text",
                "metadata": {"document_id": "fb", "page_number": 81},
                "dense_distance": 0.85,
                "bm25_score": None,
                "rrf_score": 0.02,
                "sources": ["dense"],
            },
            {
                "id": "wc_2",
                "text": "other irrelevant chunk",
                "metadata": {"document_id": "fb", "page_number": 80},
                "dense_distance": 0.88,
                "bm25_score": None,
                "rrf_score": 0.01,
                "sources": ["dense"],
            },
        ]
        ranked = rerank_candidates(
            "Who won the FIFA World Cup in 2022?",
            candidates,
            top_k=5,
            reranker_service=service,
        )
        self.assertEqual(ranked, [])

    def test_fallback_does_not_change_normal_relevance_pass(self):
        service = MagicMock()
        service.score.return_value = [4.0, 3.5, -6.0, 2.0]
        candidates = [
            {
                "id": "p10_a",
                "text": "supervised learning definition",
                "metadata": {
                    "document_id": "docA",
                    "filename": "ml.pdf",
                    "page_number": 10,
                },
                "dense_distance": 0.2,
                "bm25_score": 1.0,
                "rrf_score": 0.04,
                "sources": ["dense"],
            },
            {
                "id": "p10_b",
                "text": "more supervised learning on same page",
                "metadata": {
                    "document_id": "docA",
                    "filename": "ml.pdf",
                    "page_number": 10,
                },
                "dense_distance": 0.3,
                "bm25_score": 1.0,
                "rrf_score": 0.03,
                "sources": ["bm25"],
            },
            {
                "id": "p30_noise",
                "text": "irrelevant football",
                "metadata": {
                    "document_id": "docB",
                    "filename": "fb.pdf",
                    "page_number": 30,
                },
                "dense_distance": 1.0,
                "bm25_score": 2.0,
                "rrf_score": 0.02,
                "sources": ["bm25"],
            },
            {
                "id": "p20_good",
                "text": "decision tree entropy",
                "metadata": {
                    "document_id": "docA",
                    "filename": "ml.pdf",
                    "page_number": 20,
                },
                "dense_distance": 0.4,
                "bm25_score": 1.5,
                "rrf_score": 0.01,
                "sources": ["dense"],
            },
        ]
        ranked = rerank_candidates(
            "what is supervised learning",
            candidates,
            top_k=3,
            reranker_service=service,
        )
        self.assertEqual([c["id"] for c in ranked], ["p10_a", "p20_good"])
        self.assertTrue(all(c["relevance"] >= 25 for c in ranked))

    def test_dual_source_below_rerank_floor_still_rejected(self):
        candidates = [
            {
                "id": "dual_weak",
                "text": "entropy overlap text",
                "metadata": {"document_id": "docA", "page_number": 30},
                "reranker_score": -5.9783,
                "relevance": 0,
                "sources": ["dense", "bm25"],
            }
        ]
        self.assertEqual(select_evidence(candidates, top_k=5), [])
        self.assertTrue(has_dual_retrieval_support(candidates[0]))
        self.assertTrue(has_dual_retrieval_support(
            {"sources": ["dense", "bm25"]}
        ))


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
