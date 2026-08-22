"""Conversation persistence and isolation tests."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from backend import app
from memory.store import (
    delete_conversation,
    load_conversation,
    save_message,
)


class TestConversationPersistence(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.ids: list[str] = []

    def tearDown(self):
        for cid in self.ids:
            delete_conversation(cid)

    def test_create_list_rename_delete(self):
        created = self.client.post("/conversations", json={}).json()
        cid = created["conversation_id"]
        self.ids.append(cid)
        self.assertTrue(cid)
        self.assertEqual(created["title"], "New conversation")

        listed = self.client.get("/conversations").json()
        self.assertTrue(any(item["conversation_id"] == cid for item in listed))

        renamed = self.client.patch(
            f"/conversations/{cid}",
            json={"title": "ML notes"},
        ).json()
        self.assertEqual(renamed["title"], "ML notes")

        deleted = self.client.delete(f"/conversations/{cid}")
        self.assertEqual(deleted.status_code, 200)
        listed = self.client.get("/conversations").json()
        self.assertFalse(any(item["conversation_id"] == cid for item in listed))
        self.ids.remove(cid)

    def test_new_conversation_does_not_inherit_old_history(self):
        first = self.client.post("/conversations", json={}).json()
        second = self.client.post("/conversations", json={}).json()
        self.ids.extend([first["conversation_id"], second["conversation_id"]])

        save_message(first["conversation_id"], "user", "What is entropy?")
        save_message(first["conversation_id"], "assistant", "Entropy is disorder.")

        history_a = load_conversation(first["conversation_id"])
        history_b = load_conversation(second["conversation_id"])
        self.assertEqual(len(history_a), 2)
        self.assertEqual(len(history_b), 0)

        detail_b = self.client.get(
            f"/conversations/{second['conversation_id']}"
        ).json()
        self.assertEqual(detail_b["messages"], [])

    def test_follow_up_still_sees_previous_messages(self):
        created = self.client.post("/conversations", json={}).json()
        cid = created["conversation_id"]
        self.ids.append(cid)
        save_message(cid, "user", "What is supervised learning?")
        save_message(cid, "assistant", "Learning from labeled data.")

        detail = self.client.get(f"/conversations/{cid}").json()
        self.assertEqual(len(detail["messages"]), 2)
        self.assertEqual(detail["messages"][0]["role"], "user")
        self.assertEqual(detail["messages"][1]["role"], "assistant")
        self.assertEqual(detail["title"], "What is supervised learning?")

    def test_chat_persists_citations_with_assistant_message(self):
        created = self.client.post("/conversations", json={}).json()
        cid = created["conversation_id"]
        self.ids.append(cid)

        from unittest.mock import patch

        retrieval = {
            "chunks": ["Supervised learning uses labeled data."],
            "distances": [0.2],
            "metadata": [
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page_number": 4,
                }
            ],
            "ids": ["doc-a_1"],
            "relevances": [90],
            "reranker_scores": [2.0],
            "rerank_fallback": False,
        }
        with patch(
            "rag.retrieve_candidates",
            return_value=retrieval,
        ), patch(
            "rag.generate_response",
            return_value="Supervised learning uses labels.[E1]",
        ), patch(
            "index_hygiene.live_searchable_document_ids",
            return_value=["doc-a"],
        ):
            response = self.client.post(
                "/chat",
                json={
                    "question": "What is supervised learning?",
                    "conversation_id": cid,
                    "document_ids": ["doc-a"],
                    "mode": "normal",
                },
            )

        self.assertEqual(response.status_code, 200)
        detail = self.client.get(f"/conversations/{cid}").json()
        self.assertEqual(len(detail["messages"]), 2)
        citations = detail["messages"][1]["citations"]
        self.assertIsNotNone(citations)
        self.assertEqual(citations[0]["page"], 4)
        self.assertEqual(citations[0]["document_id"], "doc-a")


if __name__ == "__main__":
    unittest.main()
