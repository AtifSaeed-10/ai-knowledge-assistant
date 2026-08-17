"""Agentic foundation tests — no autonomous loop."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from agent_foundation import (
    TOOL_DOCUMENT_QA,
    effective_mode,
    is_agentic_enabled,
    planned_agent_steps,
    run_document_qa,
)
from backend import app
from memory.store import delete_conversation
from modes import MODE_AGENTIC, MODE_NORMAL


class TestAgenticFoundation(unittest.TestCase):
    def test_agentic_disabled_by_default(self):
        self.assertFalse(is_agentic_enabled())
        self.assertEqual(effective_mode("agentic"), MODE_NORMAL)
        self.assertEqual(effective_mode("super_focused"), "super_focused")

    def test_run_document_qa_delegates_to_ask_question(self):
        sentinel = {"answer": "ok", "sources": []}

        def fake_ask(question, history, document_ids, generate=True, mode=None):
            self.assertEqual(question, "What is entropy?")
            self.assertEqual(document_ids, ["doc-a"])
            self.assertTrue(generate)
            return sentinel

        result = run_document_qa(
            "What is entropy?",
            document_ids=["doc-a"],
            ask_question=fake_ask,
        )
        self.assertIs(result, sentinel)

    def test_planner_is_placeholder_not_an_agent(self):
        steps = planned_agent_steps("Compare the two contracts")
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["tool"], TOOL_DOCUMENT_QA)
        self.assertIn("placeholder", steps[0]["note"].lower())

    def test_agentic_api_mode_does_not_invent_agent_behavior(self):
        conversation_id = "test-agentic-fallback"
        delete_conversation(conversation_id)
        client = TestClient(app)
        retrieval = {
            "chunks": ["Supervised learning uses labeled data."],
            "distances": [0.2],
            "metadata": [
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page_number": 1,
                }
            ],
            "ids": ["doc-a_0"],
            "relevances": [90],
            "reranker_scores": [2.0],
            "rerank_fallback": False,
        }
        with patch(
            "rag.retrieve_candidates",
            return_value=retrieval,
        ) as mock_retrieve, patch(
            "rag.generate_response",
            return_value="Supervised learning uses labels.",
        ):
            response = client.post(
                "/chat",
                json={
                    "question": "What is supervised learning?",
                    "conversation_id": conversation_id,
                    "document_ids": ["doc-a", "doc-b"],
                    "mode": MODE_AGENTIC,
                },
            )

        self.assertEqual(response.status_code, 200)
        mock_retrieve.assert_called_once()
        self.assertEqual(mock_retrieve.call_args.args[1], ["doc-a", "doc-b"])
        delete_conversation(conversation_id)


if __name__ == "__main__":
    unittest.main()
