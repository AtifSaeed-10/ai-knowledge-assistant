"""Wide recall probes for plot and summary questions."""

from __future__ import annotations

import unittest

from conversation_query import INTENT_HOW, INTENT_SUMMARY, analyze_turn, detect_intent
from wide_recall import is_wide_recall_question, lexical_probe_queries
from grounding_verifier import find_context_support
from answer_prompt import build_answer_prompt


class TestWideRecall(unittest.TestCase):
    def test_apple_question_is_wide_and_probes_apple(self):
        question = (
            "What specific series of events leads to Gregor getting an apple "
            "lodged in his back, and who throws it?"
        )
        self.assertEqual(detect_intent(question), INTENT_HOW)
        self.assertTrue(is_wide_recall_question(question, INTENT_HOW))
        probes = " ".join(lexical_probe_queries(question)).lower()
        self.assertIn("apple", probes)

    def test_grete_summary_is_wide(self):
        question = (
            "Summarize the changing attitudes of Gregor's sister Grete "
            "from Chapter 1 to his death"
        )
        self.assertEqual(detect_intent(question), INTENT_SUMMARY)
        self.assertTrue(is_wide_recall_question(question, INTENT_SUMMARY))

    def test_short_definition_is_not_wide(self):
        self.assertFalse(
            is_wide_recall_question("What is supervised learning?", "definition")
        )

    def test_short_how_definition_is_not_wide(self):
        self.assertFalse(
            is_wide_recall_question("How does supervised learning work?", INTENT_HOW)
        )

    def test_who_threw_is_how_and_wide(self):
        question = "Who threw the apple that lodged in Gregor's back?"
        self.assertEqual(detect_intent(question), INTENT_HOW)
        self.assertTrue(is_wide_recall_question(question, INTENT_HOW))

    def test_why_grete_attitude_is_wide(self):
        question = "Why does Grete's attitude toward Gregor change by the end?"
        self.assertTrue(is_wide_recall_question(question, "why"))


class TestPlotGrounding(unittest.TestCase):
    def test_apple_scene_supports_plot_how_question(self):
        question = (
            "What specific series of events leads to Gregor getting an apple "
            "lodged in his back, and who throws it?"
        )
        analysis = analyze_turn(question, None)
        apple = (
            "His father had filled his pockets from the fruit bowl. He threw "
            "apple after apple. One apple lodged in Gregor's back and stayed there."
        )
        hit = find_context_support(
            question,
            sources=[
                {
                    "chunk_id": "k40",
                    "text": apple,
                    "snippet": apple[:80],
                    "page": 40,
                    "evidence_id": "E4",
                    "relevance": 80,
                }
            ],
            analysis=analysis,
        )
        self.assertTrue(hit.supported)

    def test_opening_scene_does_not_support_apple_event(self):
        question = (
            "What specific series of events leads to Gregor getting an apple "
            "lodged in his back, and who throws it?"
        )
        analysis = analyze_turn(question, None)
        opening = (
            "Gregor Samsa woke from uneasy dreams to find himself transformed "
            "in his bed into a gigantic insect. A lady in furs hung in a gilt frame."
        )
        hit = find_context_support(
            question,
            sources=[
                {
                    "chunk_id": "k1",
                    "text": opening,
                    "snippet": opening[:80],
                    "page": 1,
                    "evidence_id": "E1",
                    "relevance": 80,
                }
            ],
            analysis=analysis,
        )
        self.assertFalse(hit.supported)

    def test_plot_prompt_tells_model_to_use_later_pages(self):
        question = (
            "What specific series of events leads to Gregor getting an apple "
            "lodged in his back, and who throws it?"
        )
        analysis = analyze_turn(question, None)
        prompt = build_answer_prompt(
            question=question,
            search_query=question,
            history=None,
            chunks=[
                "His father threw apple after apple. One apple lodged in Gregor's back."
            ],
            metadata=[{"filename": "metamorphosis.pdf", "page_number": 40}],
            evidence_ids=["E1"],
            analysis=analysis,
            wide_recall=True,
        )
        lowered = prompt.lower()
        self.assertIn("later", lowered)
        self.assertNotIn("do not upgrade a definition", lowered)


if __name__ == "__main__":
    unittest.main()
