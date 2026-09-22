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

    def test_operator_has_unlimited_questions(self):
        from app_platform.quotas import service as quotas
        from app_platform.auth.dependency import resolve_context
        from test_support import make_access_token

        body = self.admin.get("/me/usage").json()
        self.assertTrue(body["unlimited"])
        self.assertEqual(body["questions_limit"], 0)
        self.assertEqual(body["web_questions_limit"], 0)
        self.assertEqual(body["pdfs_limit"], 0)

        context = resolve_context(
            f"Bearer {make_access_token('google-admin', ADMIN_EMAIL)}",
            None,
        )
        for _ in range(25):
            quotas.check_question_allowed(context)
            quotas.record_question(context)
        summary = quotas.usage_summary(context)
        self.assertEqual(summary["questions_used"], 0)
        self.assertTrue(summary["unlimited"])


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
        self.assertIn("providers", body)
        self.assertIn("answers", body)
        self.assertIn("places", body)
        self.assertIn("unanswered", body)


class TestAdminOperatorExtras(AdminApiTestCase):
    def test_operator_usage_is_unlimited_and_private_to_admin(self):
        admin_usage = self.admin.get("/me/usage").json()
        other_usage = self.other.get("/me/usage").json()
        guest_usage = self.guest.get("/me/usage").json()

        self.assertTrue(admin_usage["unlimited"])
        self.assertEqual(admin_usage["pdfs_limit"], 0)
        self.assertEqual(admin_usage["questions_limit"], 0)
        self.assertFalse(other_usage["unlimited"])
        self.assertFalse(guest_usage["unlimited"])
        self.assertNotIn("providers", other_usage)
        self.assertNotIn("places", other_usage)
        self.assertNotIn("country", other_usage)

    def test_overview_shows_which_llm_answered_and_hides_answers_from_issues(self):
        from app_platform.auth.context import user_context
        from app_platform.ops.events import record_answer, record_unanswered
        from answer_prompt import MISSING_IN_DOCUMENT_PHRASE

        self.other.get("/me/usage")
        actor = user_context(_user_id(self.other), "other@example.com")
        record_answer(
            question="What happens to Gregor?",
            actor=actor,
            provider="groq",
            model="llama-3.3-70b",
        )
        record_unanswered(
            question="Who is the president?",
            answer=MISSING_IN_DOCUMENT_PHRASE,
            actor=actor,
            provider="gemini",
            model="gemini-2.0-flash",
        )

        body = self.admin.get("/admin/overview").json()
        providers = {row["provider"]: row["count"] for row in body["providers"]}
        self.assertGreaterEqual(providers.get("groq", 0), 1)
        self.assertTrue(any(item["provider"] == "groq" for item in body["answers"]))
        self.assertFalse(any(event["kind"] == "answer" for event in body["events"]))
        self.assertTrue(
            any(item["category"] == "not_in_document" for item in body["unanswered"])
        )
        person = next(row for row in body["people"] if row["email"] == "other@example.com")
        self.assertGreaterEqual(person["answers"], 1)
        self.assertGreaterEqual(person["unanswered"], 1)

    def test_overview_records_country_from_cdn_headers(self):
        self.other.get(
            "/me/usage",
            headers={"CF-IPCountry": "PK", "CF-IPCity": "Lahore"},
        )
        body = self.admin.get("/admin/overview").json()
        person = next(row for row in body["people"] if row["email"] == "other@example.com")
        self.assertEqual(person["country"], "PK")
        self.assertEqual(person["region"], "Lahore")
        self.assertTrue(any(place["country"] == "PK" for place in body["places"]))
        self.assertNotIn("country", self.other.get("/me/usage").json())


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
