"""Item 1 — index hygiene and corpus isolation."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from database.db import init_db
from database.document_store import (
    create_document,
    delete_document,
    list_ready_document_ids,
    update_document_status,
)
from document_paths import stored_pdf_path
from index_hygiene import (
    chroma_where_for_document_ids,
    filter_hits_to_documents,
    purge_chroma_document,
    reconcile_index,
    resolve_retrieval_scope,
)
from modes import MODE_NORMAL, MODE_SUPER_FOCUSED


class TestRetrievalScope(unittest.TestCase):
    def test_normal_empty_request_uses_ready_ids_only(self):
        with patch(
            "index_hygiene.live_searchable_document_ids",
            return_value=["ready-a", "ready-b"],
        ):
            scoped, abort = resolve_retrieval_scope(MODE_NORMAL, None)
        self.assertFalse(abort)
        self.assertEqual(scoped, ["ready-a", "ready-b"])

    def test_normal_drops_deleted_and_failed_ids(self):
        with patch(
            "index_hygiene.live_searchable_document_ids",
            return_value=["ready-a"],
        ):
            scoped, abort = resolve_retrieval_scope(
                MODE_NORMAL, ["ready-a", "orphan", "failed-doc"]
            )
        self.assertFalse(abort)
        self.assertEqual(scoped, ["ready-a"])

    def test_normal_unknown_ids_search_nothing_not_all_chroma(self):
        with patch(
            "index_hygiene.live_searchable_document_ids",
            return_value=["ready-a"],
        ):
            scoped, abort = resolve_retrieval_scope(MODE_NORMAL, ["ghost"])
        self.assertFalse(abort)
        self.assertEqual(scoped, [])

    def test_super_focused_missing_selection_aborts(self):
        with patch(
            "index_hygiene.live_searchable_document_ids",
            return_value=["ready-a"],
        ):
            scoped, abort = resolve_retrieval_scope(MODE_SUPER_FOCUSED, [])
        self.assertTrue(abort)
        self.assertEqual(scoped, [])

    def test_super_focused_rejects_non_ready_selected_doc(self):
        with patch(
            "index_hygiene.live_searchable_document_ids",
            return_value=["ready-a"],
        ):
            scoped, abort = resolve_retrieval_scope(
                MODE_SUPER_FOCUSED, ["indexing-doc", "ready-a"]
            )
        self.assertTrue(abort)
        self.assertEqual(scoped, [])

    def test_super_focused_keeps_first_ready_id_only(self):
        with patch(
            "index_hygiene.live_searchable_document_ids",
            return_value=["ready-a", "ready-b"],
        ):
            scoped, abort = resolve_retrieval_scope(
                MODE_SUPER_FOCUSED, ["ready-a", "ready-b"]
            )
        self.assertFalse(abort)
        self.assertEqual(scoped, ["ready-a"])


class TestHitFiltering(unittest.TestCase):
    def test_empty_document_ids_is_not_all_corpus_where(self):
        self.assertIsNone(chroma_where_for_document_ids([]))
        self.assertIsNone(chroma_where_for_document_ids(None))

    def test_filter_drops_orphan_hits(self):
        hits = [
            {"id": "live_0", "metadata": {"document_id": "live"}},
            {"id": "orphan_0", "metadata": {"document_id": "ghost"}},
        ]
        kept = filter_hits_to_documents(hits, ["live"])
        self.assertEqual([item["id"] for item in kept], ["live_0"])

    def test_filter_none_keeps_all(self):
        hits = [{"id": "a", "metadata": {"document_id": "x"}}]
        self.assertEqual(filter_hits_to_documents(hits, None), hits)


class TestChromaPurge(unittest.TestCase):
    def test_purges_matching_ids_and_where(self):
        collection = MagicMock()
        collection.get.return_value = {
            "ids": ["keep_0", "gone_1", "gone_2"],
            "metadatas": [
                {"document_id": "keep"},
                {"document_id": "gone"},
                {"document_id": "gone"},
            ],
        }
        deleted = purge_chroma_document("gone", collection=collection)
        self.assertEqual(deleted, 2)
        collection.delete.assert_any_call(ids=["gone_1", "gone_2"])
        collection.delete.assert_any_call(where={"document_id": "gone"})


class TestReadyRegistry(unittest.TestCase):
    def setUp(self):
        init_db()
        self.ids: list[str] = []

    def tearDown(self):
        for document_id in self.ids:
            delete_document(document_id)

    def test_ready_ids_exclude_failed_and_indexing(self):
        ready = create_document("ready.pdf")
        failed = create_document("failed.pdf")
        indexing = create_document("indexing.pdf")
        self.ids.extend([ready, failed, indexing])
        update_document_status(ready, "ready")
        update_document_status(failed, "failed")
        update_document_status(indexing, "indexing")
        live = list_ready_document_ids()
        self.assertIn(ready, live)
        self.assertNotIn(failed, live)
        self.assertNotIn(indexing, live)


class TestReconcile(unittest.TestCase):
    def setUp(self):
        init_db()
        self.document_id = create_document("keep.pdf")
        update_document_status(self.document_id, "ready")

    def tearDown(self):
        delete_document(self.document_id)

    def test_deletes_chroma_rows_for_unknown_document_ids(self):
        collection = MagicMock()
        collection.get.return_value = {
            "ids": [f"{self.document_id}_0", "orphan-doc_9"],
            "metadatas": [
                {"document_id": self.document_id},
                {"document_id": "orphan-doc"},
            ],
        }
        with patch("index_hygiene._collection", return_value=collection), patch(
            "index_hygiene.delete_for_document"
        ) as evidence_delete, patch("index_hygiene.bm25_index.invalidate"):
            report = reconcile_index()
        self.assertEqual(report["chroma_deleted"], 1)
        self.assertIn("orphan-doc", report["orphan_documents"])
        collection.delete.assert_called()
        evidence_delete.assert_called_with("orphan-doc")


class TestStoredPdfPath(unittest.TestCase):
    def test_rejects_path_escape(self):
        self.assertIsNone(stored_pdf_path("../secret"))
        self.assertIsNone(stored_pdf_path("abc/../x"))

    def test_id_keyed_path_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("document_paths.DATA_DIR", tmp), patch(
                "index_hygiene.DATA_DIR", tmp
            ):
                document_id = "11111111-2222-3333-4444-555555555555"
                path = stored_pdf_path(document_id, must_exist=False)
                self.assertIsNotNone(path)
                assert path is not None
                self.assertTrue(path.endswith(f"{document_id}.pdf"))
                self.assertTrue(path.startswith(os.path.abspath(tmp)))


class TestAskQuestionIsolation(unittest.TestCase):
    def test_ask_question_super_focused_non_ready_does_not_retrieve(self):
        from rag import ask_question

        with patch(
            "index_hygiene.live_searchable_document_ids",
            return_value=["ready-a"],
        ), patch("rag.retrieve_candidates") as retrieve:
            result = ask_question(
                "What is supervised learning?",
                None,
                ["deleted-doc"],
                generate=True,
                mode="super_focused",
            )
        retrieve.assert_not_called()
        self.assertEqual(result["sources"], [])
        self.assertIn("no relevant information", result["answer"].lower())


class TestEmptyFilterDoesNotSearchAll(unittest.TestCase):
    def test_dense_returns_empty_for_empty_id_list(self):
        from hybrid_retrieval import retrieve_dense

        collection = MagicMock()
        collection.count.return_value = 10
        hits = retrieve_dense(
            "question",
            collection=collection,
            embedding_model=MagicMock(),
            document_ids=[],
            k=5,
        )
        self.assertEqual(hits, [])
        collection.query.assert_not_called()

    def test_bm25_returns_empty_for_empty_id_list(self):
        from hybrid_retrieval import retrieve_bm25

        hits = retrieve_bm25(
            "question",
            collection=MagicMock(),
            document_ids=[],
            k=5,
        )
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
