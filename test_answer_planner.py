"""Tests for answer planning."""

from __future__ import annotations

import unittest

from answer_planner import format_plan_for_prompt, plan_answer
from conversation_query import INTENT_DEFINITION, analyze_turn


class TestAnswerPlanner(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
