"""Phase 4A — Super Focused document scope and citation page metadata."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import app, _document_pdf_path
from memory.store import delete_conversation
from modes import (
    MODE_NORMAL,
    MODE_SUPER_FOCUSED,
    insufficient_context_payload,
    normalize_mode,
    resolve_document_scope,
)
from rag import _citation_page, ask_question


class TestModeScope(unittest.TestCase):
    def test_normalize_aliases(self):
        self.assertEqual(normalize_mode(None), MODE_NORMAL)
        self.assertEqual(normalize_mode("Super Focused"), MODE_SUPER_FOCUSED)
        self.assertEqual(normalize_mode("unknown"), MODE_NORMAL)

    def test_super_focused_uses_first_id_only(self):
        self.assertEqual(
            resolve_document_scope(MODE_SUPER_FOCUSED, ["doc-a", "doc-b"]),
            ["doc-a"],
        )
        self.assertIsNone(
            resolve_document_scope(MODE_SUPER_FOCUSED, [])
        )
        self.assertIsNone(
            resolve_document_scope(MODE_SUPER_FOCUSED, None)
        )

    def test_normal_preserves_ids(self):
        ids = ["doc-a", "doc-b"]
        self.assertEqual(resolve_document_scope(MODE_NORMAL, ids), ids)
        self.assertIsNone(resolve_document_scope(MODE_NORMAL, None))


class TestCitationPageMetadata(unittest.TestCase):
    def test_uses_stored_page_number(self):
        self.assertEqual(_citation_page({"page_number": 19}), 19)
        self.assertEqual(_citation_page({"page_start": 3}), 3)

    def test_does_not_fabricate_invalid_page(self):
        self.assertIsNone(_citation_page({}))
        self.assertIsNone(_citation_page({"page_number": 0}))
        self.assertIsNone(_citation_page({"page_number": -2}))
        self.assertIsNone(_citation_page({"page_number": "abc"}))
        self.assertIsNone(_citation_page(None))


class TestSuperFocusedChat(unittest.TestCase):
    def setUp(self):
        self.conversation_id = "test-super-focused"
        delete_conversation(self.conversation_id)
        self.client = TestClient(app)
        self._live = patch(
            "index_hygiene.live_searchable_document_ids",
            return_value=["doc-a", "doc-b", "football-doc"],
        )
        self._live.start()

    def tearDown(self):
        self._live.stop()
        delete_conversation(self.conversation_id)

    def _retrieval(self, document_id="doc-a"):
        return {
            "chunks": ["Supervised learning uses labeled data."],
            "distances": [0.2],
            "metadata": [
                {
                    "document_id": document_id,
                    "filename": "MACHINE LEARNING.pdf",
                    "page_number": 19,
                }
            ],
            "ids": [f"{document_id}_1"],
            "relevances": [90],
            "reranker_scores": [2.0],
            "rerank_fallback": False,
        }

    def test_in_scope_question_succeeds_and_citations_match_document(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=self._retrieval("doc-a"),
        ) as mock_retrieve, patch(
            "rag.generate_response",
            return_value="Supervised learning uses labeled examples.",
        ):
            response = self.client.post(
                "/chat",
                json={
                    "question": "What is supervised learning?",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a", "doc-b"],
                    "mode": "super_focused",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(mock_retrieve.call_count, 1)
        self.assertEqual(mock_retrieve.call_args_list[0].args[1], ["doc-a"])
        body = response.json()
        self.assertIn("supervised", body["answer"].lower())
        self.assertEqual(len(body["sources"]), 1)
        self.assertEqual(body["sources"][0]["document_id"], "doc-a")
        self.assertEqual(body["sources"][0]["page"], 19)
        self.assertEqual(body["sources"][0]["filename"], "MACHINE LEARNING.pdf")

    def test_absent_question_returns_insufficient_context(self):
        empty = {
            "chunks": [],
            "distances": [],
            "metadata": [],
            "ids": [],
            "relevances": [],
            "reranker_scores": [],
            "rerank_fallback": False,
        }
        with patch("rag.retrieve_candidates", return_value=empty) as mock_retrieve:
            response = self.client.post(
                "/chat/stream",
                json={
                    "question": "What is the capital of France?",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a"],
                    "mode": "super_focused",
                },
            )

        self.assertEqual(response.status_code, 200)
        mock_retrieve.assert_called_once()
        self.assertEqual(mock_retrieve.call_args.args[1], ["doc-a"])
        self.assertIn("no relevant information", response.text.lower())
        self.assertIn("__CITATIONS__[]__", response.text.replace("\n", ""))

    def test_other_documents_are_never_retrieved(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=self._retrieval("doc-a"),
        ) as mock_retrieve, patch(
            "backend.generate_response_stream",
            return_value=iter(["Answer from focused doc."]),
        ):
            response = self.client.post(
                "/chat/stream",
                json={
                    "question": "Who won the FIFA World Cup?",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a", "football-doc"],
                    "mode": "super_focused",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_retrieve.call_args.args[1], ["doc-a"])
        self.assertNotIn("football-doc", mock_retrieve.call_args.args[1])

    def test_no_selected_document_does_not_search_corpus(self):
        with patch("rag.retrieve_candidates") as mock_retrieve:
            response = self.client.post(
                "/chat",
                json={
                    "question": "What is supervised learning?",
                    "conversation_id": self.conversation_id,
                    "document_ids": [],
                    "mode": "super_focused",
                },
            )

        self.assertEqual(response.status_code, 200)
        mock_retrieve.assert_not_called()
        body = response.json()
        self.assertEqual(
            body["answer"],
            insufficient_context_payload()["answer"],
        )
        self.assertEqual(body["sources"], [])

    def test_normal_mode_still_passes_all_document_ids(self):
        with patch(
            "rag.retrieve_candidates",
            return_value=self._retrieval("doc-a"),
        ) as mock_retrieve, patch(
            "rag.generate_response",
            return_value="ok",
        ):
            response = self.client.post(
                "/chat",
                json={
                    "question": "What is supervised learning?",
                    "conversation_id": self.conversation_id,
                    "document_ids": ["doc-a", "doc-b"],
                    "mode": "normal",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_retrieve.call_args.args[1], ["doc-a", "doc-b"])


class TestAskQuestionCitations(unittest.TestCase):
    def test_citation_keeps_document_and_page(self):
        retrieval = {
            "chunks": ["text"],
            "distances": [0.1],
            "metadata": [
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page_number": 1,
                }
            ],
            "ids": ["doc-a_0"],
            "relevances": [80],
            "reranker_scores": [1.0],
            "rerank_fallback": False,
        }
        with patch("rag.retrieve_candidates", return_value=retrieval), patch(
            "rag.generate_response",
            return_value="ok",
        ), patch(
            "index_hygiene.live_searchable_document_ids",
            return_value=["doc-a"],
        ):
            result = ask_question("q", None, ["doc-a"], generate=True)

        self.assertEqual(result["sources"][0]["document_id"], "doc-a")
        self.assertEqual(result["sources"][0]["page"], 1)

    def test_invalid_page_is_omitted_not_fabricated(self):
        retrieval = {
            "chunks": ["text"],
            "distances": [0.1],
            "metadata": [
                {
                    "document_id": "doc-a",
                    "filename": "ml.pdf",
                    "page_number": "missing",
                }
            ],
            "ids": ["doc-a_0"],
            "relevances": [80],
            "reranker_scores": [1.0],
            "rerank_fallback": False,
        }
        with patch("rag.retrieve_candidates", return_value=retrieval), patch(
            "rag.generate_response",
            return_value="ok",
        ), patch(
            "index_hygiene.live_searchable_document_ids",
            return_value=["doc-a"],
        ):
            result = ask_question("q", None, ["doc-a"], generate=True)

        self.assertIsNone(result["sources"][0]["page"])


class TestDocumentPdfEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_unknown_document_404(self):
        response = self.client.get("/documents/not-a-real-id/file")
        self.assertEqual(response.status_code, 404)

    def test_path_escape_rejected(self):
        self.assertIsNone(_document_pdf_path("../secrets.txt"))
        self.assertIsNone(_document_pdf_path(""))

    def test_serves_pdf_when_file_exists(self):
        from database.document_store import create_document, delete_document
        from config import DATA_DIR

        os.makedirs(DATA_DIR, exist_ok=True)
        filename = "phase4a-preview-test.pdf"
        path = os.path.join(DATA_DIR, filename)
        # Minimal one-page PDF
        path_bytes = (
            b"%PDF-1.1\n"
            b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
            b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
            b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n"
            b"trailer<< /Root 1 0 R /Size 4 >>\nstartxref\n0\n%%EOF\n"
        )
        document_id = None
        try:
            with open(path, "wb") as handle:
                handle.write(path_bytes)
            document_id = create_document(filename)
            response = self.client.get(f"/documents/{document_id}/file")
            self.assertEqual(response.status_code, 200)
            self.assertIn("application/pdf", response.headers.get("content-type", ""))
            disposition = response.headers.get("content-disposition", "")
            self.assertIn("inline", disposition.lower())
        finally:
            if document_id:
                delete_document(document_id)
            if os.path.exists(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
