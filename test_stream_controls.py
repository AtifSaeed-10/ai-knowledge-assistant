"""Stop / regenerate stream-memory behavior."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import app
from memory.store import delete_conversation, load_conversation


class TestStreamStopAndRegenerate(unittest.TestCase):
    def setUp(self):
        self.conversation_id = "test-stream-controls"
        delete_conversation(self.conversation_id)
        self.client = TestClient(app)

    def tearDown(self):
        delete_conversation(self.conversation_id)

    def _retrieval(self):
        return {
            "chunks": ["Supervised learning uses labeled data."],
            "distances": [0.25],
            "metadata": [
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page_number": 10,
                }
            ],
            "ids": ["doc-a_1"],
            "relevances": [90],
            "reranker_scores": [2.0],
            "rerank_fallback": False,
        }

    def test_failed_stream_does_not_save_partial_assistant(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=self._retrieval(),
        ), patch(
            "backend.generate_response_stream",
            side_effect=RuntimeError("client cancelled"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    "/chat/stream",
                    json={
                        "question": "What is supervised learning?",
                        "conversation_id": self.conversation_id,
                        "document_ids": ["doc-a"],
                    },
                )

        history = load_conversation(self.conversation_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["role"], "user")
        self.assertNotEqual(history[0]["role"], "assistant")

    def test_complete_stream_still_saves_assistant(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=self._retrieval(),
        ), patch(
            "backend.generate_response_stream",
            return_value=iter(["Complete answer."]),
        ):
            response = self.client.post(
                "/chat/stream",
                json={
                    "question": "What is supervised learning?",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                },
            )

        self.assertEqual(response.status_code, 200)
        history = load_conversation(self.conversation_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[1]["content"], "Complete answer.")

    def test_regenerate_does_not_duplicate_user_message(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=self._retrieval(),
        ), patch(
            "backend.generate_response_stream",
            return_value=iter(["First answer."]),
        ):
            self.client.post(
                "/chat/stream",
                json={
                    "question": "What is supervised learning?",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                },
            )

        with patch(
            "rag.retrieve_candidates",
            return_value=self._retrieval(),
        ), patch(
            "backend.generate_response_stream",
            return_value=iter(["Second answer."]),
        ):
            response = self.client.post(
                "/chat/stream",
                json={
                    "question": "What is supervised learning?",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                    "regenerate": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        history = load_conversation(self.conversation_id)
        user_turns = [msg for msg in history if msg["role"] == "user"]
        assistant_turns = [msg for msg in history if msg["role"] == "assistant"]
        self.assertEqual(len(user_turns), 1)
        self.assertEqual(len(assistant_turns), 1)
        self.assertEqual(assistant_turns[0]["content"], "Second answer.")
        self.assertNotIn("First answer.", assistant_turns[0]["content"])
        self.assertIn("Second answer.", response.text)


if __name__ == "__main__":
    unittest.main()
