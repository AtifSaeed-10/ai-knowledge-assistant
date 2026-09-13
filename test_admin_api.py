"""Operator dashboard: only the allowlisted account can read everyone."""

import os
import tempfile
import unittest
from unittest.mock import patch

from app_platform import settings
from backend import app
from database.db import init_db
from database.document_store import create_document, mark_document_index_failed
from database.event_store import record_event
from test_support import api_client, new_guest_session, user_api_client


ADMIN_EMAIL = "saeedatif199@gmail.com"


class AdminApiTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_patch = patch(
            "database.connection.database_path",
            return_value=os.path.join(self._tmpdir.name, "admin.db"),
        )
        self._db_patch.start()
        init_db()

        self.auth = patch.multiple(
            settings,
            AUTH_PROVIDER="supabase",
            SUPABASE_JWT_SECRET="unit-test-jwt-secret",
            ADMIN_EMAILS=[ADMIN_EMAIL],
        )
        self.auth.start()
        self.addCleanup(self.auth.stop)

        self.guest_session = new_guest_session()
        self.guest = api_client(app, self.guest_session)
        self.other = user_api_client(app, "google-other", "other@example.com")
        self.admin = user_api_client(app, "google-admin", ADMIN_EMAIL)

    def tearDown(self):
        self._db_patch.stop()
        self._tmpdir.cleanup()


class TestAdminAccess(AdminApiTestCase):
    def test_guest_cannot_open_the_dashboard(self):
        response = self.guest.get("/admin/overview")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"]["code"], "AUTH_REQUIRED")

    def test_another_signed_in_user_is_refused(self):
        response = self.other.get("/admin/overview")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "FORBIDDEN")

    def test_usage_flags_only_the_operator(self):
        self.assertFalse(self.guest.get("/me/usage").json()["admin"])
        self.assertFalse(self.other.get("/me/usage").json()["admin"])
        self.assertTrue(self.admin.get("/me/usage").json()["admin"])


class TestAdminOverview(AdminApiTestCase):
    def test_operator_sees_guests_signed_in_users_uploads_and_errors(self):
        # Touch the guest so a trial row exists, then give them a failed PDF.
        self.guest.get("/me/usage")
        doc_id = create_document(
            "notes.pdf", owner_type="guest", owner_id=self.guest_session
        )
        mark_document_index_failed(doc_id, "Indexing failed: EmptyPDF")
        record_event(
            kind="llm",
            actor_type="guest",
            actor_id=self.guest_session,
            route="/chat",
            provider="groq",
            category="rate_limit",
            message="groq rate limited",
        )

        # Create the other signed-in profile by hitting a protected route.
        self.other.get("/me/usage")
        create_document("paper.pdf", owner_type="user", owner_id=_user_id(self.other))

        body = self.admin.get("/admin/overview").json()

        self.assertGreaterEqual(body["totals"]["signed_in_users"], 2)
        self.assertGreaterEqual(body["totals"]["guest_sessions"], 1)
        self.assertGreaterEqual(body["totals"]["pdfs"], 2)
        self.assertGreaterEqual(body["totals"]["failed_pdfs"], 1)

        labels = {person["label"] for person in body["people"]}
        self.assertIn(ADMIN_EMAIL, labels)
        self.assertIn("other@example.com", labels)
        self.assertTrue(any(person["actor_type"] == "guest" for person in body["people"]))

        filenames = {item["filename"] for item in body["uploads"]}
        self.assertIn("notes.pdf", filenames)
        self.assertIn("paper.pdf", filenames)
        failed = next(item for item in body["uploads"] if item["filename"] == "notes.pdf")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["owner_type"], "guest")

        self.assertTrue(any(event["category"] == "rate_limit" for event in body["events"]))
        self.assertIn("credit_start_usd", body["azure"])
        self.assertIn("remaining_requests", body["groq"])


def _user_id(client) -> str:
    """Resolve the internal user_id created by the first authenticated call."""
    from database.user_store import list_users

    # The client already called /me/usage, so the profile exists.
    emails = {user.get("email"): user["user_id"] for user in list_users()}
    # Prefer the non-admin helper's email when present.
    for email, user_id in emails.items():
        if email == "other@example.com":
            return user_id
    return list_users()[0]["user_id"]
