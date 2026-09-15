"""Tests for answer planning."""

from __future__ import annotations

import unittest

from answer_planner import format_plan_for_prompt, plan_answer
from conversation_query import (
    INTENT_DEFINITION,
    INTENT_KEY_POINTS,
    INTENT_MIXED,
    INTENT_SUMMARY,
    analyze_turn,
    detect_intent,
    split_conjunctive_topics,
)


class TestAnswerPlanner(unittest.TestCase):
    def test_week_lookup_adds_a_lexical_sub_query(self):
        analysis = analyze_turn("what is content of week 4", None)
        plan = plan_answer(
            "what is content of week 4",
            "what is content of week 4",
            analysis,
        )
        self.assertTrue(any(item.lower() == "week 4" for item in plan.sub_queries))

    def test_definition_question_gets_briefing_components(self):
        analysis = analyze_turn("What is supervised learning?", None)
        self.assertEqual(analysis.intent, INTENT_DEFINITION)
        plan = plan_answer("What is supervised learning?", "supervised learning", analysis)
        roles = [item.role for item in plan.components]
        self.assertIn("definition", roles)
        self.assertIn("types", roles)
        self.assertTrue(plan.briefing)
        self.assertGreaterEqual(len(plan.sub_queries), 2)

    def test_plan_formats_for_prompt(self):
        analysis = analyze_turn("What is supervised learning?", None)
        plan = plan_answer("What is supervised learning?", "supervised learning", analysis)
        text = format_plan_for_prompt(plan)
        self.assertIn("Answer plan", text)
        self.assertIn("briefing", text.lower())

    def test_summary_plan_asks_to_synthesize_not_find_a_heading(self):
        analysis = analyze_turn("Summarize the leave policy.", None)
        self.assertEqual(analysis.intent, INTENT_SUMMARY)
        plan = plan_answer("Summarize the leave policy.", "leave policy", analysis)
        roles = [item.role for item in plan.components]
        self.assertIn("summary", roles)
        self.assertTrue(plan.briefing)
        text = format_plan_for_prompt(plan)
        self.assertIn("synthesize", text.lower())
        self.assertIn("Summary", text)

    def test_key_points_plan_asks_to_synthesize_bullets(self):
        analysis = analyze_turn("Give me the key points of the leave policy.", None)
        self.assertEqual(analysis.intent, INTENT_KEY_POINTS)
        plan = plan_answer(
            "Give me the key points of the leave policy.",
            "leave policy",
            analysis,
        )
        roles = [item.role for item in plan.components]
        self.assertIn("key_points", roles)
        text = format_plan_for_prompt(plan)
        self.assertIn("synthesize", text.lower())


class TestConjunctiveTopics(unittest.TestCase):
    def test_and_also_splits_two_real_topics(self):
        parts = split_conjunctive_topics(
            "tell me about hitler early life and also tell me supervised learning"
        )
        self.assertEqual(len(parts), 2)
        self.assertIn("hitler", parts[0].lower())
        self.assertIn("supervised", parts[1].lower())

    def test_search_all_prefix_and_bare_and(self):
        parts = split_conjunctive_topics(
            "search all documents: Hitler's early life and supervised learning"
        )
        self.assertEqual(len(parts), 2)
        self.assertTrue(any("hitler" in part.lower() for part in parts))
        self.assertTrue(any("supervised" in part.lower() for part in parts))

    def test_father_and_son_stays_one_clause(self):
        parts = split_conjunctive_topics("the father and son conflict")
        self.assertEqual(parts, ["the father and son conflict"])

    def test_mixed_intent_and_plan_retrieves_each_topic(self):
        question = "search all documents: Hitler's early life and supervised learning"
        self.assertEqual(detect_intent(question), INTENT_MIXED)
        analysis = analyze_turn(question, None)
        plan = plan_answer(question, question, analysis)
        self.assertTrue(plan.multi_topic)
        joined = " ".join(plan.sub_queries).lower()
        self.assertIn("hitler", joined)
        self.assertIn("supervised", joined)
        self.assertIn("multi-topic", format_plan_for_prompt(plan).lower())


if __name__ == "__main__":
    unittest.main()
