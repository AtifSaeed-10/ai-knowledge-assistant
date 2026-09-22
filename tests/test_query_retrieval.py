"""Item 4 — query-type-aware retrieval and BM25 phrase boosts."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from bm25_index import BM25Index, contains_consecutive_phrase, tokenize
from query_retrieval import (
    KIND_ARTICLE,
    KIND_DEFAULT,
    KIND_FIGURE,
    KIND_FRONT_MATTER,
    KIND_LISTING,
    KIND_SECTION_REF,
    KIND_WHY_AUTHOR,
    classify_retrieval_query,
    ensure_typed_hits_in_pool,
    parse_section_ref,
)
from hybrid_retrieval import retrieve_candidates
from reranker import rerank_candidates


def _collection(ids, documents, metadatas):
    collection = MagicMock()
    collection.get.return_value = {
        "ids": ids,
        "documents": documents,
        "metadatas": metadatas,
    }
    return collection


class TestClassifyRetrievalQuery(unittest.TestCase):
    def test_front_matter_dedication(self):
        profile = classify_retrieval_query(
            "Who are the two scholars to whom this sixth edition is dedicated?"
        )
        self.assertEqual(profile.kind, KIND_FRONT_MATTER)
        self.assertEqual(profile.page_min, 1)
        self.assertGreaterEqual(profile.page_max, 6)
        self.assertGreater(profile.reserved_slots, 0)
        self.assertIn("sixth edition", profile.phrases)
        self.assertIn("two scholars", profile.phrases)
        self.assertNotIn("scholars sixth", profile.phrases)
        self.assertTrue(any("dedicat" in extra.lower() for extra in profile.extra_queries))

    def test_figure_number_and_which_figure(self):
        numbered = classify_retrieval_query(
            "Which figure number depicts tear gas victims?"
        )
        self.assertEqual(numbered.kind, KIND_FIGURE)
        self.assertIn("tear gas", " ".join(numbered.phrases))
        self.assertTrue(any("figure" in q for q in numbered.extra_queries))

        explicit = classify_retrieval_query("What does figure 12 show?")
        self.assertEqual(explicit.kind, KIND_FIGURE)
        self.assertEqual(explicit.figure_number, 12)
        self.assertIn("figure 12", explicit.phrases)

    def test_article_number(self):
        profile = classify_retrieval_query(
            "What does Article 231 say about war guilt?"
        )
        self.assertEqual(profile.kind, KIND_ARTICLE)
        self.assertEqual(profile.article_number, "231")
        self.assertIn("article 231", profile.phrases)
        self.assertEqual(profile.extra_queries[0].lower(), "article 231")

    def test_why_author_extracts_contrast_pair(self):
        profile = classify_retrieval_query(
            "Why does the author use Nanking instead of Nanjing?"
        )
        self.assertEqual(profile.kind, KIND_WHY_AUTHOR)
        joined = " ".join(profile.phrases).lower()
        self.assertIn("nanking", joined)
        self.assertIn("nanjing", joined)

    def test_week_number_is_a_section_lookup(self):
        profile = classify_retrieval_query(
            "what is content of week 4"
        )
        self.assertEqual(profile.kind, KIND_SECTION_REF)
        self.assertEqual(profile.section_label, "week")
        self.assertEqual(profile.section_number, "4")
        self.assertIn("week 4", profile.phrases)
        self.assertGreater(profile.reserved_slots, 0)
        self.assertTrue(any("week 4" in item.lower() for item in profile.extra_queries))
        self.assertEqual(parse_section_ref("What's in lecture four?"), ("lecture", "4"))

    def test_listing_and_count(self):
        profile = classify_retrieval_query(
            "What were the five long-term causes of World War I?"
        )
        self.assertEqual(profile.kind, KIND_LISTING)
        self.assertGreater(profile.candidate_k_boost, 0)
        self.assertIn("long term", " ".join(profile.phrases))

    def test_default_definition_is_not_front_matter(self):
        profile = classify_retrieval_query("What is supervised learning?")
        self.assertEqual(profile.kind, KIND_DEFAULT)
        self.assertIsNone(profile.page_max)
        self.assertIn("supervised learning", profile.phrases)

    def test_plot_event_gets_rare_noun_probes(self):
        profile = classify_retrieval_query(
            "What specific series of events leads to Gregor getting an apple "
            "lodged in his back, and who throws it?"
        )
        extras = " ".join(profile.extra_queries).lower()
        self.assertIn("apple", extras)
        self.assertGreater(profile.reserved_slots, 0)


class TestEnsureTypedHitsInPool(unittest.TestCase):
    def test_reserves_slots_for_missed_front_matter_chunk(self):
        fused = [
            {
                "id": f"late_{i}",
                "text": f"later chapter {i}",
                "metadata": {"page_number": 20 + i},
                "rrf_score": 0.02,
                "sources": ["dense"],
            }
            for i in range(5)
        ]
        typed = [
            {
                "id": "front_6",
                "text": "This edition is dedicated to two scholars.",
                "metadata": {"page_number": 6},
                "bm25_score": 8.0,
                "rank": 1,
            }
        ]
        merged = ensure_typed_hits_in_pool(
            fused,
            typed,
            reserved=4,
            limit=5,
        )
        ids = [item["id"] for item in merged]
        self.assertIn("front_6", ids)
        self.assertEqual(ids[0], "front_6")
        self.assertEqual(len(merged), 5)
        self.assertIn("query_type", merged[0]["sources"])

    def test_default_pool_unchanged_when_no_typed_hits(self):
        fused = [{"id": "a", "text": "x", "metadata": {}, "rrf_score": 0.1, "sources": ["dense"]}]
        self.assertEqual(
            ensure_typed_hits_in_pool(fused, [], reserved=4, limit=5),
            fused,
        )


class TestBM25PhraseAndPageFilter(unittest.TestCase):
    def test_consecutive_phrase_helper(self):
        tokens = tokenize("Article 231 assigned war guilt to Germany.")
        self.assertTrue(contains_consecutive_phrase(tokens, "article 231"))
        self.assertFalse(contains_consecutive_phrase(tokens, "article guilt"))

    def test_phrase_boost_ranks_contiguous_article_span_first(self):
        collection = _collection(
            ["art_231", "guilt_later"],
            [
                "Article 231 of the treaty assigned responsibility to Germany.",
                "This article reviews German war guilt without citing 231.",
            ],
            [
                {"document_id": "ww2", "page_number": 40},
                {"document_id": "ww2", "page_number": 90},
            ],
        )
        index = BM25Index()
        index.ensure_loaded(collection)
        boosted = index.search(
            "What does Article 231 say?",
            k=5,
            phrases=["article 231"],
        )
        self.assertEqual(boosted[0]["id"], "art_231")
        self.assertGreater(boosted[0]["bm25_score"], 0)
        # Toy corpora often assign IDF 0 to terms that appear in every doc,
        # so the unboosted search may drop both hits (score <= 0).

    def test_page_max_keeps_front_matter_and_drops_later_scholars(self):
        collection = _collection(
            ["p6", "p100"],
            [
                "This sixth edition is dedicated to scholars Showalter and Vandervort.",
                "Later chapters cite many scholars of military history.",
            ],
            [
                {"document_id": "ww2", "page_number": 6},
                {"document_id": "ww2", "page_number": 100},
            ],
        )
        index = BM25Index()
        index.ensure_loaded(collection)
        front = index.search(
            "Who are the two scholars to whom this sixth edition is dedicated?",
            k=5,
            phrases=["sixth edition", "dedicated to"],
            page_min=1,
            page_max=8,
        )
        self.assertEqual([h["id"] for h in front], ["p6"])
        later = index.search(
            "later chapters",
            k=5,
            phrases=["later chapters"],
            page_min=9,
        )
        self.assertEqual([h["id"] for h in later], ["p100"])


class TestRetrieveCandidatesQueryType(unittest.TestCase):
    def test_front_matter_query_exposes_kind_and_can_inject_page_six(self):
        collection = _collection(
            ["p6", "p80"],
            [
                "This sixth edition is dedicated to scholars Showalter and Vandervort.",
                "Scholars debate alliance plans in later chapters.",
            ],
            [
                {"document_id": "ww2", "filename": "ww2.pdf", "page_number": 6},
                {"document_id": "ww2", "filename": "ww2.pdf", "page_number": 80},
            ],
        )
        dense_only_late = [
            {
                "id": "p80",
                "text": "Scholars debate alliance plans in later chapters.",
                "metadata": {
                    "document_id": "ww2",
                    "filename": "ww2.pdf",
                    "page_number": 80,
                },
                "dense_distance": 0.2,
                "rank": 1,
            }
        ]
        service = MagicMock()
        service.model_name = "BAAI/bge-reranker-base"
        service.score.return_value = [0.1, 4.0]

        with patch(
            "hybrid_retrieval.retrieve_dense",
            return_value=dense_only_late,
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
                "Who are the two scholars to whom this sixth edition is dedicated?",
                collection=collection,
                embedding_model=MagicMock(),
                top_k=5,
            )

        self.assertEqual(result["query_kind"], KIND_FRONT_MATTER)
        self.assertIn("p6", result["ids"])
        self.assertIn(6, result["retrieval_pages"])
        self.assertFalse(result["zero_result"])

    def test_default_query_does_not_force_front_matter_kind(self):
        collection = _collection(
            ["ml1"],
            ["Supervised learning uses labeled examples."],
            [{"document_id": "ml", "page_number": 10}],
        )
        dense = [
            {
                "id": "ml1",
                "text": "Supervised learning uses labeled examples.",
                "metadata": {"document_id": "ml", "page_number": 10},
                "dense_distance": 0.1,
                "rank": 1,
            }
        ]
        service = MagicMock()
        service.model_name = "BAAI/bge-reranker-base"
        service.score.return_value = [5.0]

        with patch("hybrid_retrieval.retrieve_dense", return_value=dense), patch(
            "hybrid_retrieval.rerank_candidates",
            side_effect=lambda query, fused, **kwargs: rerank_candidates(
                query,
                fused,
                reranker_service=service,
                **kwargs,
            ),
        ):
            result = retrieve_candidates(
                "What is supervised learning?",
                collection=collection,
                embedding_model=MagicMock(),
                top_k=5,
            )
        self.assertEqual(result["query_kind"], KIND_DEFAULT)
        self.assertIsNone(result.get("page_max"))


if __name__ == "__main__":
    unittest.main()
