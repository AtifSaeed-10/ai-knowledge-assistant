"""Item 3 — reranker calibration, adaptive gating, pre-LLM wrong-page tracking."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from config import (
    CITATION_MIN_RELEVANCE,
    EVIDENCE_MIN_RELEVANCE,
    RERANKER_MODEL_MINILM,
)
from hybrid_retrieval import retrieve_candidates
from rerank_calibration import (
    AUDIT_HELD_OUT_MINILM,
    adaptive_keep_candidates,
    calibrated_relevance,
    is_minilm_reranker,
    pre_llm_rank_diagnostics,
    wrong_page_pre_llm,
    zero_result_when_fused,
)
from reranker import rerank_candidates, select_evidence, sigmoid_relevance


def _scored(
    chunk_id: str,
    *,
    page: int,
    score: float,
    relevance: int,
    sources: list[str] | None = None,
    text: str | None = None,
) -> dict:
    return {
        "id": chunk_id,
        "text": text or f"passage {chunk_id}",
        "metadata": {"document_id": "doc", "page_number": page},
        "reranker_score": score,
        "relevance": relevance,
        "rrf_score": 0.02,
        "sources": sources or ["dense"],
    }


class TestHeldOutMiniLMCalibration(unittest.TestCase):
    def test_offset_splits_audit_true_positives_from_true_negatives(self):
        self.assertTrue(is_minilm_reranker(RERANKER_MODEL_MINILM))
        self.assertFalse(is_minilm_reranker("BAAI/bge-reranker-base"))

        for case in AUDIT_HELD_OUT_MINILM:
            raw = float(case["raw_score"])
            unshifted = sigmoid_relevance(raw)
            shifted = calibrated_relevance(raw, RERANKER_MODEL_MINILM)
            if case["must_clear_evidence_floor"]:
                self.assertLess(unshifted, EVIDENCE_MIN_RELEVANCE, case["case_id"])
                self.assertGreaterEqual(shifted, EVIDENCE_MIN_RELEVANCE, case["case_id"])
            else:
                self.assertLess(shifted, EVIDENCE_MIN_RELEVANCE, case["case_id"])
            if case["must_clear_citation_floor"]:
                self.assertGreaterEqual(shifted, CITATION_MIN_RELEVANCE, case["case_id"])
            else:
                self.assertLess(shifted, CITATION_MIN_RELEVANCE, case["case_id"])

    def test_bge_does_not_apply_minilm_offset(self):
        raw = -4.4518
        self.assertEqual(
            calibrated_relevance(raw, "BAAI/bge-reranker-base"),
            sigmoid_relevance(raw),
        )


class TestAdaptiveGating(unittest.TestCase):
    def test_near_tie_below_floor_stays_in_recall_pool(self):
        top = _scored("treaty", page=18, score=-0.5, relevance=38)
        near = _scored("assassination", page=27, score=-1.4, relevance=20)
        far = _scored("noise", page=80, score=-6.0, relevance=0)
        kept, path = adaptive_keep_candidates([top, near, far])
        self.assertEqual(path, "floor_or_tie")
        self.assertEqual([c["id"] for c in kept], ["treaty", "assassination"])
        self.assertTrue(near.get("rerank_tie"))
        self.assertFalse(top.get("rerank_tie"))

    def test_strong_top_still_drops_far_noise(self):
        good = _scored("ml", page=10, score=4.0, relevance=98)
        noise = _scored("fb", page=30, score=-6.0, relevance=0)
        kept, path = adaptive_keep_candidates([good, noise])
        self.assertEqual(path, "floor_or_tie")
        self.assertEqual([c["id"] for c in kept], ["ml"])


class TestMiniLMRerankPipeline(unittest.TestCase):
    def test_entropy_minilm_becomes_citeable_without_dual_source(self):
        service = MagicMock()
        service.model_name = RERANKER_MODEL_MINILM
        service.score.return_value = [-4.4518, -5.5941]
        candidates = [
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
        ranked = rerank_candidates(
            "Why is lower entropy better when choosing a split?",
            candidates,
            top_k=5,
            reranker_service=service,
        )
        self.assertEqual([c["id"] for c in ranked], ["entropy_93"])
        self.assertFalse(ranked[0]["recall_fallback"])
        self.assertTrue(ranked[0]["citation_eligible"])
        self.assertGreaterEqual(ranked[0]["relevance"], CITATION_MIN_RELEVANCE)
        self.assertEqual(ranked[0]["gating_path"], "floor_or_tie")

    def test_world_cup_minilm_stays_recall_only(self):
        service = MagicMock()
        service.model_name = RERANKER_MODEL_MINILM
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
        self.assertGreaterEqual(len(ranked), 1)
        self.assertTrue(all(c.get("recall_fallback") for c in ranked))
        self.assertTrue(all(not c.get("citation_eligible") for c in ranked))
        self.assertTrue(
            all(int(c.get("relevance") or 0) < EVIDENCE_MIN_RELEVANCE for c in ranked)
        )


class TestPreLLMWrongPage(unittest.TestCase):
    def test_rank1_wrong_page_is_flagged_before_llm(self):
        selected = [
            _scored("treaty", page=18, score=2.0, relevance=88),
            _scored("assassination", page=27, score=1.2, relevance=77),
        ]
        diag = pre_llm_rank_diagnostics(selected)
        self.assertEqual(diag["rank1_page"], 18)
        self.assertEqual(diag["rank1_id"], "treaty")
        self.assertEqual(diag["retrieval_pages"], [18, 27])
        self.assertAlmostEqual(diag["score_gap_12"], 0.8)
        self.assertTrue(wrong_page_pre_llm(selected, expected_page=27))
        self.assertFalse(wrong_page_pre_llm(selected, expected_page=18))

    def test_empty_selection_is_not_a_wrong_page(self):
        self.assertFalse(wrong_page_pre_llm([], expected_page=27))
        self.assertTrue(zero_result_when_fused(20, 0))
        self.assertFalse(zero_result_when_fused(20, 5))
        self.assertFalse(zero_result_when_fused(0, 0))

    def test_retrieve_candidates_exposes_pre_llm_diagnostics(self):
        dense = [
            {
                "id": "treaty_18",
                "text": "Treaty of Versailles terms",
                "metadata": {
                    "document_id": "ww2",
                    "filename": "ww2_history.pdf",
                    "page_number": 18,
                },
                "dense_distance": 0.2,
                "rank": 1,
            },
            {
                "id": "assassin_27",
                "text": "Assassination of Franz Ferdinand",
                "metadata": {
                    "document_id": "ww2",
                    "filename": "ww2_history.pdf",
                    "page_number": 27,
                },
                "dense_distance": 0.3,
                "rank": 2,
            },
        ]
        service = MagicMock()
        service.model_name = "BAAI/bge-reranker-base"
        service.score.return_value = [3.0, 1.5]

        with patch("hybrid_retrieval.retrieve_dense", return_value=dense), patch(
            "hybrid_retrieval.retrieve_bm25",
            return_value=[],
        ), patch(
            "hybrid_retrieval.rerank_candidates",
            side_effect=lambda query, fused, **kwargs: rerank_candidates(
                query,
                fused,
                reranker_service=service,
                **kwargs,
            ),
        ):
            result = retrieve_candidates(
                "What event triggered World War I?",
                collection=MagicMock(),
                embedding_model=MagicMock(),
                top_k=5,
            )

        self.assertEqual(result["rank1_page"], 18)
        self.assertEqual(result["rank1_id"], "treaty_18")
        self.assertIn(27, result["retrieval_pages"])
        self.assertFalse(result["zero_result"])
        self.assertGreaterEqual(result["fused_count"], 1)
        self.assertTrue(
            wrong_page_pre_llm(
                [
                    {
                        "id": result["rank1_id"],
                        "metadata": {"page_number": result["rank1_page"]},
                        "reranker_score": result["reranker_scores"][0],
                    }
                ],
                expected_page=27,
            )
        )


class TestSelectEvidenceTieAnnotation(unittest.TestCase):
    def test_select_evidence_keeps_near_tie_and_marks_gating_path(self):
        selected = select_evidence(
            [
                _scored("treaty", page=18, score=-0.5, relevance=38),
                _scored("assassination", page=27, score=-1.4, relevance=20),
            ],
            top_k=5,
        )
        self.assertEqual([c["id"] for c in selected], ["treaty", "assassination"])
        self.assertEqual(selected[0]["gating_path"], "floor_or_tie")
        self.assertTrue(selected[1].get("rerank_tie"))
        self.assertTrue(selected[0]["citation_eligible"])
        self.assertFalse(selected[1]["citation_eligible"])


if __name__ == "__main__":
    unittest.main()
