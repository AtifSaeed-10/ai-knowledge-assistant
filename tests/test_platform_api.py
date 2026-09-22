"""
API-level checks for the guest trial and per-actor isolation.

These go through the real routes, so they cover the dependency wiring and
HTTP status contract that the frontend branches on.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from app_platform import settings
from app_platform.auth.guest import GUEST_SESSION_HEADER
from backend import app
from database.db import init_db
from database.document_store import create_document, update_document_status
from test_support import api_client, new_guest_session, user_api_client


class PlatformApiTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_patch = patch(
            "database.connection.database_path",
            return_value=os.path.join(self._tmpdir.name, "api.db"),
        )
        self._db_patch.start()
        init_db()

        self.session_a = new_guest_session()
        self.session_b = new_guest_session()
        self.client_a = api_client(app, self.session_a)
        self.client_b = api_client(app, self.session_b)

    def tearDown(self):
        self._db_patch.stop()
        self._tmpdir.cleanup()

    def ready_document(self, filename, session_id) -> str:
        document_id = create_document(filename, owner_type="guest", owner_id=session_id)
        update_document_status(document_id, "ready")
        return document_id


class TestIdentityRequired(PlatformApiTestCase):
    def test_health_needs_no_identity(self):
        response = api_client(app).get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_a_request_without_a_session_is_refused(self):
        from fastapi.testclient import TestClient

        response = TestClient(app).get("/documents")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["code"], "AUTH_REQUIRED")


class TestUsageEndpoint(PlatformApiTestCase):
    def test_usage_reports_the_guest_allowance(self):
        with patch.multiple(
            settings, QUOTA_GUEST_MAX_PDFS=1, QUOTA_GUEST_MAX_QUESTIONS=15
        ):
            body = self.client_a.get("/me/usage").json()

        self.assertEqual(body["tier"], "guest")
        self.assertEqual(body["pdfs_limit"], 1)
        self.assertEqual(body["questions_limit"], 15)
        self.assertEqual(body["questions_used"], 0)
        self.assertEqual(body["questions_window"], "trial")

    def test_usage_counts_only_the_callers_documents(self):
        self.ready_document("a.pdf", self.session_a)
        self.ready_document("b.pdf", self.session_b)

        self.assertEqual(self.client_a.get("/me/usage").json()["pdfs_used"], 1)
        self.assertEqual(self.client_b.get("/me/usage").json()["pdfs_used"], 1)


class TestUploadQuota(PlatformApiTestCase):
    def test_a_second_guest_upload_is_refused_with_a_quota_error(self):
        self.ready_document("first.pdf", self.session_a)

        with patch.object(settings, "QUOTA_GUEST_MAX_PDFS", 1):
            response = self.client_a.post(
                "/upload",
                files={"file": ("second.pdf", b"%PDF-1.4 fake", "application/pdf")},
            )

        self.assertEqual(response.status_code, 402)
        detail = response.json()["detail"]
        self.assertEqual(detail["code"], "QUOTA_EXCEEDED")
        self.assertEqual(detail["resource"], "pdfs")
        self.assertEqual(detail["upgrade_hint"], "sign_in")


class TestChatQuota(PlatformApiTestCase):
    def test_the_question_after_the_limit_is_refused_before_retrieval(self):
        self.ready_document("a.pdf", self.session_a)

        with patch.multiple(settings, QUOTA_GUEST_MAX_QUESTIONS=0), patch(
            "backend.ask_question"
        ) as never_called:
            response = self.client_a.post(
                "/chat/stream",
                json={
                    "question": "What is this about?",
                    "conversation_id": "conv-quota-test",
                },
            )

        self.assertEqual(response.status_code, 402)
        self.assertEqual(response.json()["detail"]["resource"], "questions")
        # A refused question must not reach the RAG pipeline or the LLM.
        never_called.assert_not_called()


class TestDocumentIsolation(PlatformApiTestCase):
    def setUp(self):
        super().setUp()
        self.doc_a = self.ready_document("a.pdf", self.session_a)
        self.doc_b = self.ready_document("b.pdf", self.session_b)

    def test_the_library_lists_only_your_own_documents(self):
        listing = self.client_a.get("/documents").json()
        self.assertEqual([doc["document_id"] for doc in listing], [self.doc_a])

    def test_another_actors_document_detail_is_forbidden(self):
        self.assertEqual(
            self.client_a.get(f"/documents/{self.doc_a}").status_code, 200
        )
        response = self.client_a.get(f"/documents/{self.doc_b}")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "FORBIDDEN")

    def test_another_actors_pdf_cannot_be_downloaded(self):
        self.assertEqual(
            self.client_a.get(f"/documents/{self.doc_b}/file").status_code, 403
        )

    def test_another_actors_evidence_is_forbidden(self):
        self.assertEqual(
            self.client_a.get(
                f"/documents/{self.doc_b}/chunks/{self.doc_b}_0/evidence"
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client_a.get(f"/documents/{self.doc_b}/evidence-summary").status_code,
            403,
        )

    def test_another_actors_document_cannot_be_deleted(self):
        self.assertEqual(
            self.client_a.delete(f"/documents/{self.doc_b}").status_code, 403
        )
        # It is still there for its owner.
        self.assertEqual(
            self.client_b.get(f"/documents/{self.doc_b}").status_code, 200
        )

    def test_a_foreign_document_id_never_reaches_retrieval(self):
        with patch("backend.ask_question") as ask:
            self.client_a.post(
                "/chat",
                json={
                    "question": "What does the other document say?",
                    "conversation_id": "conv-scope-test",
                    "document_ids": [self.doc_b],
                    "mode": "normal",
                },
            )

        # Every requested document belonged to someone else, so the request
        # short-circuits instead of widening to the whole corpus.
        ask.assert_not_called()

    def test_your_own_document_id_is_passed_through_to_retrieval(self):
        with patch("backend.ask_question") as ask:
            ask.return_value = {"answer": "ok", "sources": []}
            self.client_a.post(
                "/chat",
                json={
                    "question": "What does my document say?",
                    "conversation_id": "conv-scope-ok",
                    "document_ids": [self.doc_a, self.doc_b],
                    "mode": "normal",
                },
            )

        ask.assert_called_once()
        self.assertEqual(ask.call_args.args[2], [self.doc_a])


class TestConversationIsolation(PlatformApiTestCase):
    def setUp(self):
        super().setUp()
        self.conv_b = self.client_b.post(
            "/conversations", json={"title": "b chat"}
        ).json()["conversation_id"]

    def test_the_sidebar_lists_only_your_own_conversations(self):
        self.client_a.post("/conversations", json={"title": "a chat"})

        titles = [item["title"] for item in self.client_a.get("/conversations").json()]
        self.assertEqual(titles, ["a chat"])

    def test_another_actors_conversation_cannot_be_opened(self):
        self.assertEqual(
            self.client_b.get(f"/conversations/{self.conv_b}").status_code, 200
        )
        self.assertEqual(
            self.client_a.get(f"/conversations/{self.conv_b}").status_code, 403
        )

    def test_another_actors_conversation_cannot_be_renamed_or_deleted(self):
        self.assertEqual(
            self.client_a.patch(
                f"/conversations/{self.conv_b}", json={"title": "hijacked"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client_a.delete(f"/conversations/{self.conv_b}").status_code, 403
        )
        self.assertEqual(
            self.client_a.delete(f"/memory/{self.conv_b}").status_code, 403
        )

        detail = self.client_b.get(f"/conversations/{self.conv_b}").json()
        self.assertEqual(detail["title"], "b chat")


class TestMigrateGuestRoute(PlatformApiTestCase):
    def test_migration_requires_a_signed_in_caller(self):
        response = self.client_a.post(
            "/auth/migrate-guest",
            headers={GUEST_SESSION_HEADER: self.session_a},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["code"], "AUTH_REQUIRED")


class TestAccountWorkspaces(PlatformApiTestCase):
    """
    The product contract: each Google account keeps its own PDFs and chats,
    a guest trial can be claimed once, and signing back in restores history.
    """

    def setUp(self):
        super().setUp()
        self.auth = patch.multiple(
            settings,
            AUTH_PROVIDER="supabase",
            SUPABASE_JWT_SECRET="unit-test-jwt-secret",
        )
        self.auth.start()
        self.addCleanup(self.auth.stop)

        self.doc_id = self.ready_document("trial.pdf", self.session_a)
        self.conv_id = self.client_a.post(
            "/conversations", json={"title": "trial chat"}
        ).json()["conversation_id"]

        self.user_a = user_api_client(
            app, "google-a", "a@example.com", guest_session=self.session_a
        )
        self.user_b = user_api_client(
            app, "google-b", "b@example.com", guest_session=self.session_a
        )

    def _document_ids(self, client):
        return [item["document_id"] for item in client.get("/documents").json()]

    def _conversation_ids(self, client):
        return [item["conversation_id"] for item in client.get("/conversations").json()]

    def test_first_sign_in_claims_the_guest_pdf_and_chat(self):
        body = self.user_a.post("/auth/migrate-guest").json()
        self.assertEqual(body["documents_moved"], 1)
        self.assertEqual(body["conversations_moved"], 1)
        self.assertFalse(body["already_migrated"])

        self.assertEqual(self._document_ids(self.user_a), [self.doc_id])
        self.assertEqual(self._conversation_ids(self.user_a), [self.conv_id])
        self.assertEqual(self._document_ids(self.client_a), [])
        self.assertEqual(self._conversation_ids(self.client_a), [])

    def test_second_account_cannot_take_or_see_the_first_account_library(self):
        self.user_a.post("/auth/migrate-guest")

        body = self.user_b.post("/auth/migrate-guest").json()
        self.assertEqual(body["documents_moved"], 0)
        self.assertEqual(body["conversations_moved"], 0)
        self.assertTrue(body["already_migrated"])

        self.assertEqual(self._document_ids(self.user_b), [])
        self.assertEqual(self._conversation_ids(self.user_b), [])
        self.assertEqual(self.user_b.get(f"/documents/{self.doc_id}").status_code, 403)
        self.assertEqual(
            self.user_b.get(f"/conversations/{self.conv_id}").status_code, 403
        )
        self.assertEqual(self._document_ids(self.user_a), [self.doc_id])
        self.assertEqual(self._conversation_ids(self.user_a), [self.conv_id])

    def test_signing_back_in_restores_that_account_history(self):
        self.user_a.post("/auth/migrate-guest")

        again = user_api_client(app, "google-a", "a@example.com")
        self.assertEqual(self._document_ids(again), [self.doc_id])
        self.assertEqual(self._conversation_ids(again), [self.conv_id])
        self.assertEqual(again.get(f"/conversations/{self.conv_id}").status_code, 200)

    def test_guest_files_are_claimed_even_without_a_trial_row(self):
        orphan = new_guest_session()
        doc = self.ready_document("orphan.pdf", orphan)
        claimant = user_api_client(
            app, "google-c", "c@example.com", guest_session=orphan
        )

        body = claimant.post("/auth/migrate-guest").json()
        self.assertEqual(body["documents_moved"], 1)
        self.assertEqual(self._document_ids(claimant), [doc])
        self.assertNotIn(doc, self._document_ids(self.user_a))

    def test_a_new_guest_trial_can_be_claimed_by_the_next_account(self):
        self.user_a.post("/auth/migrate-guest")

        later_guest = new_guest_session()
        later_guest_client = api_client(app, later_guest)
        later_guest_client.get("/me/usage")
        later_doc = self.ready_document("later.pdf", later_guest)
        later_user = user_api_client(
            app, "google-b", "b@example.com", guest_session=later_guest
        )

        body = later_user.post("/auth/migrate-guest").json()
        self.assertEqual(body["documents_moved"], 1)
        self.assertEqual(self._document_ids(later_user), [later_doc])
        self.assertEqual(self._document_ids(self.user_a), [self.doc_id])
        self.assertNotIn(later_doc, self._document_ids(self.user_a))

    def test_two_signed_in_accounts_keep_separate_uploads(self):
        from app_platform.auth.dependency import resolve_context
        from test_support import make_access_token

        self.user_a.post("/auth/migrate-guest")

        context_b = resolve_context(
            f"Bearer {make_access_token('google-b', 'b@example.com')}", None
        )
        b_doc = create_document(
            "b-only.pdf",
            owner_type=context_b.actor_type,
            owner_id=context_b.actor_id,
        )
        update_document_status(b_doc, "ready")

        self.assertEqual(self._document_ids(self.user_a), [self.doc_id])
        self.assertEqual(self._document_ids(self.user_b), [b_doc])
        self.assertNotIn(self.doc_id, self._document_ids(self.user_b))


if __name__ == "__main__":
    unittest.main()
