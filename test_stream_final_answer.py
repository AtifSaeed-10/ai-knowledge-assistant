"""Item 9: a repaired refusal reaches the client, not just the saved history."""

from __future__ import annotations

import json
import re
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from answer_prompt import MISSING_IN_DOCUMENT_PHRASE
from backend import app
from memory.store import delete_conversation, load_conversation


ANSWER_FINAL_START = "__ANSWER_FINAL__"
ANSWER_FINAL_END = "__END_ANSWER_FINAL__"

NOTICE_CHUNK = (
    "Either party may terminate the agreement by giving thirty days written "
    "notice to the other party's registered office."
)
KITCHEN_CHUNK = (
    "The office kitchen is stocked with tea, coffee, and biscuits for staff."
)

_FRAME_RE = re.compile(
    re.escape(ANSWER_FINAL_START) + r"(.*?)" + re.escape(ANSWER_FINAL_END),
    re.DOTALL,
)


def _retrieval(chunks: list[str], pages: list[int], relevances: list[int], ids: list[str]):
    return {
        "chunks": chunks,
        "distances": [0.2] * len(chunks),
        "metadata": [
            {
                "document_id": "handbook",
                "filename": "staff_handbook.pdf",
                "page_number": page,
            }
            for page in pages
        ],
        "ids": ids,
        "relevances": relevances,
        "reranker_scores": [1.0] * len(chunks),
        "citation_eligible": [rel >= 30 for rel in relevances],
        "rerank_fallback": False,
    }


def _final_answers(body: str) -> list[str]:
    return [json.loads(match) for match in _FRAME_RE.findall(body)]


class TestStreamFinalAnswerFrame(unittest.TestCase):
    def setUp(self):
        self.conversation_id = "test-stream-final-answer"
        delete_conversation(self.conversation_id)
        self.client = TestClient(app)
        self._live = patch(
            "index_hygiene.live_searchable_document_ids",
            return_value=["handbook"],
        )
        self._live.start()

    def tearDown(self):
        self._live.stop()
        delete_conversation(self.conversation_id)

    def _stream(self, question: str, retrieval: dict, streamed: str, retry: str):
        with patch("rag.retrieve_candidates", return_value=retrieval), patch(
            "backend.generate_response_stream",
            return_value=iter([streamed]),
        ), patch("backend.generate_response", return_value=retry):
            response = self.client.post(
                "/chat/stream",
                json={
                    "question": question,
                    "conversation_id": self.conversation_id,
                    "document_ids": ["handbook"],
                },
            )
        self.assertEqual(response.status_code, 200)
        return response.text

    def test_repaired_refusal_is_sent_as_a_final_answer_frame(self):
        body = self._stream(
            "How much notice is required to end the agreement?",
            _retrieval([NOTICE_CHUNK, KITCHEN_CHUNK], [12, 40], [88, 9], ["h_12", "h_40"]),
            MISSING_IN_DOCUMENT_PHRASE,
            MISSING_IN_DOCUMENT_PHRASE,
        )

        finals = _final_answers(body)
        self.assertEqual(len(finals), 1)
        self.assertIn("thirty days", finals[0].lower())
        self.assertNotIn("couldn't find", finals[0].lower())

        history = load_conversation(self.conversation_id)
        assistant = [turn for turn in history if turn["role"] == "assistant"]
        self.assertEqual(len(assistant), 1)
        # What the user sees must equal what was persisted.
        self.assertEqual(assistant[0]["content"], finals[0])

    def test_retry_repair_is_sent_as_a_final_answer_frame(self):
        retry = "The agreement ends with thirty days written notice. [E1]"
        body = self._stream(
            "How much notice is required to end the agreement?",
            _retrieval([NOTICE_CHUNK], [12], [88], ["h_12"]),
            MISSING_IN_DOCUMENT_PHRASE,
            retry,
        )

        finals = _final_answers(body)
        self.assertEqual(len(finals), 1)
        self.assertIn("thirty days", finals[0].lower())

    def test_kept_refusal_sends_no_final_answer_frame(self):
        body = self._stream(
            "Who won the World Cup?",
            _retrieval([KITCHEN_CHUNK], [40], [4], ["h_40"]),
            MISSING_IN_DOCUMENT_PHRASE,
            MISSING_IN_DOCUMENT_PHRASE,
        )

        self.assertEqual(_final_answers(body), [])
        self.assertIn(MISSING_IN_DOCUMENT_PHRASE, body)

    def test_grounded_answer_sends_no_final_answer_frame(self):
        answer = "Either party may end the agreement with thirty days notice. [E1]"
        body = self._stream(
            "How much notice is required to end the agreement?",
            _retrieval([NOTICE_CHUNK], [12], [88], ["h_12"]),
            answer,
            answer,
        )

        self.assertEqual(_final_answers(body), [])
        self.assertIn("thirty days", body)

    def test_frame_payload_survives_newlines_and_quotes(self):
        body = self._stream(
            "How much notice is required to end the agreement?",
            _retrieval([NOTICE_CHUNK], [12], [88], ["h_12"]),
            MISSING_IN_DOCUMENT_PHRASE,
            MISSING_IN_DOCUMENT_PHRASE,
        )

        finals = _final_answers(body)
        self.assertEqual(len(finals), 1)
        # The frame carries JSON, so raw newlines never leak into the protocol.
        raw = _FRAME_RE.search(body).group(1)
        self.assertNotIn("\n", raw)
        self.assertIn("\n", finals[0])


if __name__ == "__main__":
    unittest.main()
