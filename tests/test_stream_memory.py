"""Regression tests for streaming memory and retrieval logging."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from test_support import api_client

from backend import app
from memory.store import delete_conversation, load_conversation
from retrieval_logger import log_retrieval


class TestRetrievalLoggerNoneDistance(unittest.TestCase):
    def test_logs_none_dense_distance_without_crashing(self):
        log_path = "logs/retrieval.log"
        if os.path.exists(log_path):
            os.remove(log_path)

        log_retrieval(
            "test question",
            ["chunk text"],
            [None],
            ["chunk_1"],
            [{"document_id": "d1", "page_number": 1}],
        )

        with open(log_path, encoding="utf-8") as file:
            content = file.read()

        self.assertIn("DISTANCE: None", content)


class TestStreamMemoryPersistence(unittest.TestCase):
    def setUp(self):
        self.conversation_id = "test-stream-memory-regression"
        delete_conversation(self.conversation_id)
        self.client = api_client(app)
        self._live = patch(
            "index_hygiene.live_searchable_document_ids",
            return_value=["doc-a", "doc-b"],
        )
        self._live.start()

    def tearDown(self):
        self._live.stop()
        delete_conversation(self.conversation_id)

    def _retrieval_result(self):
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

    def test_stream_saves_user_and_assistant_once(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=self._retrieval_result(),
        ), patch(
            "backend.generate_response_stream",
            return_value=iter(["First answer."]),
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
        body = response.text
        self.assertIn("__CITATIONS__", body)
        self.assertIn("First answer.", body)

        history = load_conversation(self.conversation_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "What is supervised learning?")
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[1]["content"], "First answer.")

    def test_second_stream_request_receives_saved_history_for_rewrite(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=self._retrieval_result(),
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
            return_value=self._retrieval_result(),
        ), patch(
            "backend.generate_response_stream",
            return_value=iter(["Follow-up answer."]),
        ), patch(
            "rag.rewrite_query",
            return_value="What is supervised learning in simple terms?",
        ) as mock_rewrite:
            response = self.client.post(
                "/chat/stream",
                json={
                    "question": "Explain it simply.",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                },
            )

        self.assertEqual(response.status_code, 200)
        mock_rewrite.assert_called_once()
        history_arg = mock_rewrite.call_args[0][1]
        self.assertEqual(len(history_arg), 2)
        self.assertEqual(history_arg[0]["content"], "What is supervised learning?")
        self.assertEqual(history_arg[1]["content"], "First answer.")

        history = load_conversation(self.conversation_id)
        self.assertEqual(len(history), 4)


class TestUnanswerableMiniLMPath(unittest.TestCase):
    def test_france_question_does_not_crash_with_none_distances(self):
        from rag import ask_question

        retrieval = {
            "chunks": ["irrelevant football text", "92"],
            "distances": [1.1, None],
            "metadata": [
                {
                    "document_id": "doc-b",
                    "filename": "fb.pdf",
                    "page_number": 3,
                },
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page_number": 30,
                },
            ],
            "ids": ["doc-b_1", "doc-a_92"],
            "relevances": [0, 0],
            "reranker_scores": [-8.5, -11.0],
            "rerank_fallback": False,
        }

        with patch(
            "rag.retrieve_candidates",
            return_value=retrieval,
        ), patch(
            "rag.generate_response",
            return_value=(
                "I don't have enough information in the provided context."
            ),
        ):
            result = ask_question(
                "What is the capital of France?",
                None,
                ["doc-a", "doc-b"],
                generate=True,
            )

        self.assertIn(
            "don't have enough information",
            result["answer"].lower(),
        )
        self.assertEqual(len(result["sources"]), 0)

    def test_stream_unanswerable_returns_citations_protocol(self):
        self.conversation_id = "test-stream-unanswerable"
        delete_conversation(self.conversation_id)
        client = api_client(app)

        retrieval = {
            "chunks": [],
            "distances": [],
            "metadata": [],
            "ids": [],
            "relevances": [],
            "reranker_scores": [],
            "rerank_fallback": False,
        }

        with patch(
            "rag.retrieve_candidates",
            return_value=retrieval,
        ):
            response = client.post(
                "/chat/stream",
                json={
                    "question": "What is the capital of France?",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-b"],
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertTrue(body.startswith("__CITATIONS__"))
        self.assertIn("__END_CITATIONS__", body)
        citation_json = body.split("__CITATIONS__", 1)[1].split(
            "__END_CITATIONS__", 1
        )[0]
        citations = json.loads(citation_json)
        self.assertEqual(len(citations), 0)
        self.assertIn(
            "no relevant information",
            body.lower(),
        )

        delete_conversation(self.conversation_id)


if __name__ == "__main__":
    unittest.main()
