"""General conversational RAG quality regressions (no live LLM required)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from answer_prompt import (
    MISSING_IN_DOCUMENT_PHRASE,
    build_answer_prompt,
    format_evidence_passages,
)
from conversation_query import (
    INTENT_EXAMPLE,
    INTENT_HOW,
    INTENT_LISTING,
    INTENT_MIXED,
    INTENT_SIMPLIFICATION,
    INTENT_SUMMARY,
    INTENT_WHY,
    RELATION_CONTINUE,
    RELATION_NEW,
    RELATION_TRANSFORM,
    analyze_turn,
    compose_followup_query,
    detect_intent,
)
from rag import _dedupe_sources, ask_question


def _history_supervised():
    return [
        {"role": "user", "content": "What is supervised learning?"},
        {
            "role": "assistant",
            "content": (
                "Supervised learning trains models from labeled examples. "
                "Two common forms are classification and regression."
            ),
        },
    ]


class TestTurnAnalysis(unittest.TestCase):
    def test_pronoun_follow_up_needs_rewrite(self):
        analysis = analyze_turn("Why is it useful?", _history_supervised())
        self.assertTrue(analysis.needs_rewrite)
        self.assertEqual(analysis.relation, RELATION_CONTINUE)
        self.assertEqual(analysis.intent, INTENT_WHY)

    def test_style_transform_follow_up_needs_rewrite(self):
        analysis = analyze_turn("Explain it simply.", _history_supervised())
        self.assertTrue(analysis.needs_rewrite)
        self.assertEqual(analysis.relation, RELATION_TRANSFORM)
        self.assertEqual(analysis.intent, INTENT_SIMPLIFICATION)

    def test_example_request_without_topic_needs_rewrite(self):
        analysis = analyze_turn("Give me an example.", _history_supervised())
        self.assertTrue(analysis.needs_rewrite)
        self.assertEqual(analysis.intent, INTENT_EXAMPLE)
        self.assertEqual(analysis.relation, RELATION_TRANSFORM)

    def test_ordinal_follow_up_needs_rewrite(self):
        analysis = analyze_turn("Explain the first one.", _history_supervised())
        self.assertTrue(analysis.needs_rewrite)
        self.assertEqual(analysis.relation, RELATION_CONTINUE)

    def test_self_contained_question_skips_rewrite(self):
        analysis = analyze_turn(
            "What is the difference between classification and regression?",
            _history_supervised(),
        )
        self.assertFalse(analysis.needs_rewrite)
        self.assertTrue(analysis.relation in {RELATION_CONTINUE, RELATION_NEW})

    def test_topic_switch_skips_rewrite(self):
        analysis = analyze_turn(
            "What is a red card in football?",
            _history_supervised(),
        )
        self.assertFalse(analysis.needs_rewrite)
        self.assertEqual(analysis.relation, RELATION_NEW)

    def test_no_history_skips_rewrite(self):
        analysis = analyze_turn("What is entropy?", None)
        self.assertFalse(analysis.needs_rewrite)
        self.assertEqual(analysis.relation, RELATION_NEW)

    def test_mixed_multi_part_intent(self):
        intent = detect_intent(
            "Explain clustering, list its types, and compare it with classification."
        )
        self.assertEqual(intent, INTENT_MIXED)

    def test_summary_and_how_intents(self):
        self.assertEqual(detect_intent("Summarize that."), INTENT_SUMMARY)
        self.assertEqual(detect_intent("How does it work?"), INTENT_HOW)

    def test_taxonomy_follow_up_is_listing_not_mixed(self):
        self.assertEqual(detect_intent("What are its types?"), INTENT_LISTING)
        analysis = analyze_turn("What are its types?", _history_supervised())
        self.assertTrue(analysis.needs_rewrite)
        self.assertEqual(analysis.intent, INTENT_LISTING)
        composed = compose_followup_query(
            "What are its types?",
            _history_supervised(),
            analysis,
        )
        self.assertIsNotNone(composed)
        self.assertIn("supervised learning", composed.lower())
        self.assertNotIn("machine learning", composed.lower())

    def test_ordinal_resolves_against_previous_list(self):
        analysis = analyze_turn("Explain the first one.", _history_supervised())
        composed = compose_followup_query(
            "Explain the first one.",
            _history_supervised(),
            analysis,
        )
        self.assertIsNotNone(composed)
        self.assertIn("classification", composed.lower())

    def test_document_aspect_follow_up_is_not_a_topic_switch(self):
        analysis = analyze_turn(
            "Does the document mention any limitations?",
            _history_supervised(),
        )
        self.assertTrue(analysis.needs_rewrite)
        self.assertNotEqual(analysis.relation, RELATION_NEW)

    def test_example_request_composes_current_subject(self):
        analysis = analyze_turn("Is there an example?", _history_supervised())
        self.assertTrue(analysis.needs_rewrite)
        self.assertEqual(analysis.intent, INTENT_EXAMPLE)
        composed = compose_followup_query(
            "Is there an example?",
            _history_supervised(),
            analysis,
        )
        self.assertIsNotNone(composed)
        self.assertIn("example", composed.lower())
        self.assertIn("supervised learning", composed.lower())


class TestAskQuestionConversationRouting(unittest.TestCase):
    def _retrieval(self, text="Supervised learning uses labeled data.", page=10):
        return {
            "chunks": [text],
            "distances": [0.2],
            "metadata": [
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page_number": page,
                }
            ],
            "ids": ["doc-a_1"],
            "relevances": [90],
            "reranker_scores": [2.0],
            "rerank_fallback": False,
        }

    def test_follow_up_calls_rewriter_and_retrieves_rewritten_query(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=self._retrieval(),
        ) as mock_retrieve, patch(
            "rag.rewrite_query",
            return_value="Why is supervised learning useful?",
        ) as mock_rewrite, patch(
            "rag.generate_response",
            return_value="It is useful when labels are available.",
        ):
            ask_question(
                "Why is it useful?",
                _history_supervised(),
                ["doc-a"],
                generate=True,
            )

        mock_rewrite.assert_called_once()
        self.assertEqual(
            mock_retrieve.call_args.args[0],
            "Why is supervised learning useful?",
        )

    def test_topic_switch_does_not_call_rewriter(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=self._retrieval("A red card is a sending-off.", 47),
        ) as mock_retrieve, patch(
            "rag.rewrite_query",
            return_value="SHOULD NOT BE USED",
        ) as mock_rewrite, patch(
            "rag.generate_response",
            return_value="A red card dismisses a player.",
        ):
            result = ask_question(
                "What is a red card in football?",
                _history_supervised(),
                ["doc-a", "doc-b"],
                generate=True,
            )

        mock_rewrite.assert_not_called()
        self.assertEqual(
            mock_retrieve.call_args.args[0],
            "What is a red card in football?",
        )
        self.assertNotIn("SHOULD NOT BE USED", result["prompt"])


class TestGroundedPrompt(unittest.TestCase):
    def test_prompt_separates_conversation_from_evidence(self):
        analysis = analyze_turn("Give me an example.", _history_supervised())
        prompt = build_answer_prompt(
            question="Give me an example.",
            search_query="Give an example of supervised learning",
            history=_history_supervised(),
            chunks=["The document uses house-price prediction as an example."],
            metadata=[{"filename": "ml.pdf", "page_number": 12}],
            ids=["doc-a_3"],
            relevances=[88],
            analysis=analysis,
            mode="normal",
        )
        self.assertIn("reference resolution only", prompt.lower())
        self.assertIn("Source: ml.pdf, p. 12", prompt)
        self.assertNotIn("Passage 1", prompt)
        self.assertIn("house-price prediction", prompt)
        self.assertIn("Give me an example.", prompt)
        self.assertIn("example", prompt.lower())
        self.assertNotIn("relevance: 88", prompt.lower())

    def test_super_focused_prompt_forbids_outside_examples(self):
        analysis = analyze_turn("Give me an example.", _history_supervised())
        prompt = build_answer_prompt(
            question="Give me an example.",
            search_query="example of supervised learning",
            history=_history_supervised(),
            chunks=["Supervised learning uses labeled data."],
            metadata=[{"filename": "ml.pdf", "page_number": 3}],
            analysis=analysis,
            mode="super_focused",
        )
        self.assertIn("SUPER FOCUSED", prompt)
        self.assertIn("world knowledge", prompt.lower())
        self.assertIn("Never fabricate an example", prompt)

    def test_why_prompt_does_not_treat_definition_as_reason(self):
        analysis = analyze_turn("Why is it useful?", _history_supervised())
        prompt = build_answer_prompt(
            question="Why is it useful?",
            search_query="Why is supervised learning useful?",
            history=_history_supervised(),
            chunks=["Supervised learning is learning from labeled data."],
            metadata=[{"filename": "ml.pdf", "page_number": 2}],
            analysis=analysis,
            mode="normal",
        )
        self.assertIn("definition is not enough", prompt.lower())
        self.assertIn(MISSING_IN_DOCUMENT_PHRASE, prompt)

    def test_mixed_request_asks_for_partial_answers(self):
        analysis = analyze_turn(
            "Explain clustering, list its types, and compare it with classification.",
            None,
        )
        prompt = build_answer_prompt(
            question="Explain clustering, list its types, and compare it with classification.",
            search_query="Explain clustering, list its types, and compare it with classification.",
            history=None,
            chunks=["Clustering groups unlabeled examples."],
            metadata=[{"filename": "ml.pdf", "page_number": 8}],
            analysis=analysis,
            mode="normal",
        )
        self.assertIn("multi-part", prompt.lower())
        self.assertIn("unsupported", prompt.lower())

    def test_labeled_evidence_does_not_invent_pages(self):
        text = format_evidence_passages(
            ["alpha"],
            [{"filename": "ml.pdf", "page_number": "missing"}],
        )
        self.assertIn("page unknown", text)
        self.assertNotIn("p. 1", text)

    def test_evidence_ids_label_passages(self):
        text = format_evidence_passages(
            ["alpha", "beta"],
            [
                {"filename": "ml.pdf", "page_number": 4},
                {"filename": "ml.pdf", "page_number": 5},
            ],
            ids=["c1", "c2"],
            evidence_ids=["E1", None],
        )
        self.assertIn("[E1] ml.pdf, p. 4", text)
        self.assertIn("Source: ml.pdf, p. 5", text)

    def test_prompt_requests_verbatim_quotes_not_coordinates(self):
        analysis = analyze_turn("What is supervised learning?", None)
        prompt = build_answer_prompt(
            question="What is supervised learning?",
            search_query="What is supervised learning?",
            history=None,
            chunks=["Supervised learning uses labeled examples."],
            metadata=[{"filename": "ml.pdf", "page_number": 3}],
            evidence_ids=["E1"],
            analysis=analysis,
            mode="normal",
        )
        self.assertIn('[E1:"supervised learning uses labeled examples"]', prompt)
        self.assertIn("verbatim quote", prompt)
        self.assertIn("PDF coordinates", prompt)
        self.assertIn("Never invent an id", prompt)
        self.assertIn("complete briefing", prompt)
        self.assertIn("never pile", prompt.lower())
        self.assertIn("two to four", prompt)


class TestCitationDedupeAndGrounding(unittest.TestCase):
    def test_same_page_distinct_chunks_are_not_collapsed(self):
        sources = _dedupe_sources(
            [
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page": 10,
                    "chunk_id": "doc-a_1",
                    "relevance": 90,
                },
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page": 10,
                    "chunk_id": "doc-a_2",
                    "relevance": 80,
                },
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page": 20,
                    "chunk_id": "doc-a_3",
                    "relevance": 70,
                },
            ]
        )
        self.assertEqual([item["chunk_id"] for item in sources], ["doc-a_1", "doc-a_2", "doc-a_3"])

    def test_empty_retrieval_has_no_citations(self):
        with patch(
            "rag.retrieve_candidates",
            return_value={
                "chunks": [],
                "distances": [],
                "metadata": [],
                "ids": [],
                "relevances": [],
                "reranker_scores": [],
                "rerank_fallback": False,
            },
        ):
            result = ask_question(
                "Who won the FIFA World Cup?",
                None,
                ["doc-a"],
                generate=True,
            )
        self.assertEqual(result["sources"], [])
        self.assertIn("No relevant information", result["answer"])

    def test_surviving_citations_keep_real_page_metadata(self):
        retrieval = {
            "chunks": ["Strong evidence about entropy.", "Weaker nearby sentence."],
            "distances": [0.2, 0.4],
            "metadata": [
                {"document_id": "doc-a", "filename": "ml.pdf", "page_number": 4},
                {"document_id": "doc-a", "filename": "ml.pdf", "page_number": 4},
            ],
            "ids": ["doc-a_1", "doc-a_2"],
            "relevances": [92, 40],
            "reranker_scores": [3.0, 0.2],
            "rerank_fallback": False,
        }
        with patch("rag.retrieve_candidates", return_value=retrieval), patch(
            "rag.generate_response",
            return_value="Entropy measures uncertainty.",
        ):
            result = ask_question("What is entropy?", None, ["doc-a"], generate=True)

        self.assertEqual(len(result["sources"]), 2)
        self.assertEqual(result["sources"][0]["evidence_id"], "E1")
        self.assertEqual(result["sources"][1]["evidence_id"], "E2")
        self.assertEqual(result["sources"][0]["chunk_id"], "doc-a_1")
        self.assertEqual(result["sources"][1]["chunk_id"], "doc-a_2")
        self.assertEqual(result["sources"][0]["page"], 4)
        self.assertEqual(result["sources"][0]["document_id"], "doc-a")
        self.assertIn("Strong evidence about entropy.", result["prompt"])
        self.assertIn("Weaker nearby sentence.", result["prompt"])


def _history_without_subject():
    return [
        {"role": "user", "content": "And that?"},
        {"role": "assistant", "content": "See above."},
    ]


class TestRewriteSanitization(unittest.TestCase):
    def test_rewrite_falls_back_when_model_answers(self):
        from query_rewriter import rewrite_query

        with patch(
            "query_rewriter.generate_response",
            return_value="Supervised learning is a machine learning approach that...",
        ):
            result = rewrite_query(
                "Why is it useful?",
                _history_without_subject(),
            )
        self.assertEqual(result, "Why is it useful?")

    def test_rewrite_strips_quotes(self):
        from query_rewriter import rewrite_query

        with patch(
            "query_rewriter.generate_response",
            return_value='"Why is supervised learning useful?"',
        ):
            result = rewrite_query(
                "Why is it useful?",
                _history_without_subject(),
            )
        self.assertEqual(result, "Why is supervised learning useful?")

    def test_deterministic_compose_skips_llm(self):
        from query_rewriter import rewrite_query

        with patch(
            "query_rewriter.generate_response",
            return_value="SHOULD NOT BE USED",
        ) as mock_llm:
            result = rewrite_query(
                "Why is it useful?",
                _history_supervised(),
                analysis=analyze_turn("Why is it useful?", _history_supervised()),
            )
        mock_llm.assert_not_called()
        self.assertIn("supervised learning", result.lower())
        self.assertIn("why", result.lower())


if __name__ == "__main__":
    unittest.main()
