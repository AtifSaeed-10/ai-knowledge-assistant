"""Item 2 — recall-first retrieval: nonempty fused pool never yields 0 LLM slots."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from hybrid_retrieval import retrieve_candidates
from reranker import (
    is_citation_eligible,
    rerank_candidates,
    select_evidence,
    sigmoid_relevance,
)


def _chunk(
    chunk_id: str,
    *,
    page: int,
    text: str,
    score: float,
    sources: list[str],
    relevance: int | None = None,
    rrf: float = 0.02,
    document_id: str = "ww2",
) -> dict:
    return {
        "id": chunk_id,
        "text": text,
        "metadata": {
            "document_id": document_id,
            "filename": "ww2_history.pdf",
            "page_number": page,
        },
        "dense_distance": 0.6,
        "bm25_score": 2.0 if "bm25" in sources else None,
        "rrf_score": rrf,
        "sources": list(sources),
        "reranker_score": score,
        "relevance": sigmoid_relevance(score) if relevance is None else relevance,
    }


class TestRecallFirstSelectEvidence(unittest.TestCase):
    def test_empty_candidates_stay_empty(self):
        self.assertEqual(select_evidence([], top_k=5), [])

    def test_nanking_style_low_scores_keep_target_in_recall_pool(self):
        target = _chunk(
            "ww2_21",
            page=19,
            text="Nanking is also spelled Nanjing in later scholarship.",
            score=-6.1,
            sources=["dense"],
        )
        noise = [
            _chunk(
                f"ww2_{i}",
                page=i,
                text=f"unrelated wartime chronology paragraph {i}",
                score=-8.0 - (i * 0.05),
                sources=["dense"],
            )
            for i in range(1, 16)
            if i != 19
        ]
        selected = select_evidence([target, *noise], top_k=5)
        self.assertGreaterEqual(len(selected), 1)
        self.assertIn("ww2_21", [item["id"] for item in selected])
        self.assertTrue(all(item["recall_fallback"] for item in selected))
        self.assertTrue(all(not item["citation_eligible"] for item in selected))

    def test_quality_hits_do_not_fill_remaining_slots_with_noise(self):
        good = _chunk(
            "ml_10",
            page=10,
            text="Supervised learning uses labeled examples.",
            score=4.0,
            sources=["dense"],
            document_id="ml",
        )
        noise = _chunk(
            "fb_30",
            page=30,
            text="irrelevant football offside rule",
            score=-6.0,
            sources=["bm25"],
            document_id="fb",
        )
        selected = select_evidence([good, noise], top_k=5)
        self.assertEqual([item["id"] for item in selected], ["ml_10"])
        self.assertFalse(selected[0]["recall_fallback"])
        self.assertTrue(selected[0]["citation_eligible"])

    def test_war_guilt_style_stays_in_recall_but_not_citation_pool(self):
        # Dual-source MiniLM rescue: in context, below CITATION_MIN_RELEVANCE.
        item = _chunk(
            "ww2_article_231",
            page=40,
            text="Article 231 assigned war guilt to Germany.",
            score=-1.2,
            sources=["dense", "bm25"],
            relevance=22,
        )
        selected = select_evidence([item], top_k=5)
        self.assertEqual(len(selected), 1)
        self.assertFalse(selected[0]["recall_fallback"])
        self.assertFalse(is_citation_eligible(selected[0]))
        self.assertFalse(selected[0]["citation_eligible"])


class TestRecallFirstRerank(unittest.TestCase):
    def test_score_floor_does_not_empty_nonempty_pool(self):
        service = MagicMock()
        service.model_name = "BAAI/bge-reranker-base"
        service.score.return_value = [-3.0, -4.0]
        candidates = [
            {
                "id": "a",
                "text": "passage a",
                "metadata": {"document_id": "d", "page_number": 1},
                "dense_distance": 0.4,
                "bm25_score": None,
                "rrf_score": 0.03,
                "sources": ["dense"],
            },
            {
                "id": "b",
                "text": "passage b",
                "metadata": {"document_id": "d", "page_number": 2},
                "dense_distance": 0.5,
                "bm25_score": None,
                "rrf_score": 0.02,
                "sources": ["dense"],
            },
        ]
        ranked = rerank_candidates(
            "naming note Nanjing",
            candidates,
            top_k=5,
            min_score=10.0,
            reranker_service=service,
        )
        self.assertGreaterEqual(len(ranked), 1)
        self.assertTrue(all(item.get("recall_fallback") for item in ranked))
        self.assertTrue(all(not item.get("citation_eligible") for item in ranked))

    def test_rerank_empty_input_stays_empty(self):
        service = MagicMock()
        ranked = rerank_candidates(
            "anything",
            [],
            top_k=5,
            reranker_service=service,
        )
        self.assertEqual(ranked, [])
        service.score.assert_not_called()


class TestRecallFirstRetrieveCandidates(unittest.TestCase):
    def test_empty_document_ids_still_search_nothing(self):
        result = retrieve_candidates(
            "Nanjing spelling",
            collection=MagicMock(),
            embedding_model=MagicMock(),
            document_ids=[],
        )
        self.assertEqual(result["chunks"], [])
        self.assertEqual(result["fused_count"], 0)
        self.assertFalse(result["recall_fallback"])
        self.assertEqual(result["citation_eligible"], [])

    def test_empty_fused_pool_stays_empty(self):
        with patch("hybrid_retrieval.retrieve_dense", return_value=[]), patch(
            "hybrid_retrieval.retrieve_bm25",
            return_value=[],
        ):
            result = retrieve_candidates(
                "Nanjing spelling",
                collection=MagicMock(),
                embedding_model=MagicMock(),
                top_k=5,
            )
        self.assertEqual(result["chunks"], [])
        self.assertEqual(result["fused_count"], 0)
        self.assertFalse(result["recall_fallback"])

    def test_fused_nonempty_low_rerank_returns_recall_pool(self):
        fused_hits = [
            {
                "id": "ww2_21",
                "text": "Nanking is also spelled Nanjing in later scholarship.",
                "metadata": {
                    "document_id": "ww2",
                    "filename": "ww2_history.pdf",
                    "page_number": 19,
                },
                "dense_distance": 0.55,
                "rank": 1,
            },
            {
                "id": "ww2_5",
                "text": "figure list of chemical weapons",
                "metadata": {
                    "document_id": "ww2",
                    "filename": "ww2_history.pdf",
                    "page_number": 5,
                },
                "dense_distance": 0.58,
                "rank": 2,
            },
        ]
        service = MagicMock()
        service.score.return_value = [-6.2, -7.1]

        with patch(
            "hybrid_retrieval.retrieve_dense",
            return_value=fused_hits,
        ), patch(
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
                "Does the book use the spelling Nanjing?",
                collection=MagicMock(),
                embedding_model=MagicMock(),
                top_k=5,
            )

        self.assertGreaterEqual(result["fused_count"], 1)
        self.assertGreaterEqual(len(result["ids"]), 1)
        self.assertIn("ww2_21", result["ids"])
        self.assertTrue(result["recall_fallback"])
        self.assertTrue(all(not flag for flag in result["citation_eligible"]))
        self.assertEqual(len(result["chunks"]), len(result["ids"]))

    def test_safety_net_when_rerank_returns_empty_on_fused_pool(self):
        dense = [
            {
                "id": "keep_me",
                "text": "Nanjing naming note",
                "metadata": {
                    "document_id": "ww2",
                    "filename": "ww2_history.pdf",
                    "page_number": 19,
                },
                "dense_distance": 0.4,
                "rank": 1,
            }
        ]
        with patch("hybrid_retrieval.retrieve_dense", return_value=dense), patch(
            "hybrid_retrieval.retrieve_bm25",
            return_value=[],
        ), patch(
            "hybrid_retrieval.rerank_candidates",
            return_value=[],
        ):
            result = retrieve_candidates(
                "Nanjing",
                collection=MagicMock(),
                embedding_model=MagicMock(),
                top_k=5,
            )

        self.assertEqual(result["fused_count"], 1)
        self.assertEqual(result["ids"], ["keep_me"])
        self.assertGreaterEqual(len(result["chunks"]), 1)


if __name__ == "__main__":
    unittest.main()
