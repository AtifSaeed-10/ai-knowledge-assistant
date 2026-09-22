"""Unit checks for Groq header parsing and Azure credit estimates."""

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app_platform import settings
from app_platform.ops.azure import azure_status
from app_platform.ops.groq_limits import parse_groq_limits, usage_tokens


class TestGroqLimits(unittest.TestCase):
    def test_reads_rate_limit_headers_case_insensitively(self):
        limits = parse_groq_limits(
            {
                "X-Ratelimit-Remaining-Requests": "28",
                "x-ratelimit-limit-requests": "30",
                "x-ratelimit-remaining-tokens": "12000",
                "x-ratelimit-limit-tokens": "15000",
                "x-ratelimit-reset-requests": "2s",
            }
        )
        self.assertEqual(limits["remaining_requests"], 28)
        self.assertEqual(limits["limit_requests"], 30)
        self.assertEqual(limits["remaining_tokens"], 12000)
        self.assertEqual(limits["reset_requests"], "2s")

    def test_usage_tokens_reads_total(self):
        class Usage:
            total_tokens = 42

        class Response:
            usage = Usage()

        self.assertEqual(usage_tokens(Response()), 42)
        self.assertEqual(usage_tokens(object()), 0)


class TestAzureStatus(unittest.TestCase):
    def test_manual_spend_wins(self):
        with patch.multiple(
            settings,
            AZURE_CREDIT_START_USD=100.0,
            AZURE_SPEND_USD=12.5,
            AZURE_CREDIT_STARTED_AT="",
        ):
            body = azure_status()
        self.assertEqual(body["source"], "manual")
        self.assertEqual(body["spend_usd"], 12.5)
        self.assertEqual(body["remaining_usd"], 87.5)

    def test_unknown_without_start_or_spend(self):
        with patch.multiple(
            settings,
            AZURE_CREDIT_START_USD=100.0,
            AZURE_SPEND_USD=None,
            AZURE_CREDIT_STARTED_AT="",
        ):
            body = azure_status()
        self.assertEqual(body["source"], "unknown")
        self.assertIsNone(body["remaining_usd"])

    def test_estimate_from_start_date(self):
        started = datetime.now(timezone.utc) - timedelta(days=10)
        with patch.multiple(
            settings,
            AZURE_CREDIT_START_USD=100.0,
            AZURE_VM_HOURLY_USD=0.05,
            AZURE_SPEND_USD=None,
            AZURE_CREDIT_STARTED_AT=started.isoformat(),
        ):
            body = azure_status()
        self.assertEqual(body["source"], "estimate")
        self.assertAlmostEqual(body["spend_usd"], 12.0, delta=0.2)
        self.assertAlmostEqual(body["remaining_usd"], 88.0, delta=0.2)


class TestUnansweredKinds(unittest.TestCase):
    def test_classifies_document_refusals(self):
        from answer_prompt import (
            INSUFFICIENT_CONTEXT_PHRASE,
            MISSING_EXAMPLE_PHRASE,
            MISSING_IN_DOCUMENT_PHRASE,
        )
        from app_platform.ops.unanswered import unanswered_category

        self.assertEqual(unanswered_category(MISSING_IN_DOCUMENT_PHRASE), "not_in_document")
        self.assertEqual(unanswered_category(INSUFFICIENT_CONTEXT_PHRASE), "not_enough_context")
        self.assertEqual(unanswered_category(MISSING_EXAMPLE_PHRASE), "missing_example")
        self.assertEqual(unanswered_category("Gregor turned into an insect."), None)

    def test_empty_answer_is_its_own_kind(self):
        from app_platform.ops.unanswered import unanswered_category

        self.assertEqual(unanswered_category(""), "empty_answer")


class TestRequestLocation(unittest.TestCase):
    def test_reads_cloudflare_country_and_city(self):
        from starlette.requests import Request

        from app_platform.ops.location import location_from_request

        request = Request(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/",
                "raw_path": b"/",
                "query_string": b"",
                "headers": [
                    (b"cf-ipcountry", b"DE"),
                    (b"cf-ipcity", b"Berlin"),
                ],
                "client": ("127.0.0.1", 1),
                "server": ("test", 80),
            }
        )
        self.assertEqual(location_from_request(request), ("DE", "Berlin"))

    def test_skips_unknown_country_codes(self):
        from starlette.requests import Request

        from app_platform.ops.location import location_from_request

        request = Request(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/",
                "raw_path": b"/",
                "query_string": b"",
                "headers": [(b"cf-ipcountry", b"XX")],
                "client": ("127.0.0.1", 1),
                "server": ("test", 80),
            }
        )
        self.assertEqual(location_from_request(request), (None, None))


class IsolatedAdminDbTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._db_patch = patch(
            "database.connection.database_path",
            return_value=os.path.join(self._tmpdir.name, "admin.db"),
        )
        self._db_patch.start()
        from database.db import init_db

        init_db()

    def tearDown(self):
        self._db_patch.stop()
        self._tmpdir.cleanup()


class TestAdminUnlimitedQuota(IsolatedAdminDbTestCase):
    def test_allowlisted_gmail_has_no_question_or_upload_cap(self):
        from app_platform.auth.context import user_context
        from app_platform.quotas.service import (
            check_question_allowed,
            check_upload_allowed,
            usage_summary,
        )

        admin = user_context("admin-1", "saeedatif199@gmail.com")
        other = user_context("user-2", "other@example.com")
        with patch.object(settings, "ADMIN_EMAILS", ["saeedatif199@gmail.com"]):
            admin_usage = usage_summary(admin)
            other_usage = usage_summary(other)
            check_question_allowed(admin)
            check_upload_allowed(admin)

        self.assertTrue(admin_usage["admin"])
        self.assertTrue(admin_usage["unlimited"])
        self.assertEqual(admin_usage["pdfs_limit"], 0)
        self.assertEqual(admin_usage["questions_limit"], 0)
        self.assertFalse(other_usage["unlimited"])
        self.assertGreater(other_usage["pdfs_limit"], 0)


class TestAdminOverviewPayload(IsolatedAdminDbTestCase):
    def test_shows_llm_answers_places_and_unanswered_kinds(self):
        from answer_prompt import MISSING_IN_DOCUMENT_PHRASE
        from app_platform.auth.context import user_context
        from app_platform.ops.events import record_answer, record_unanswered
        from app_platform.ops.overview import admin_overview
        from database.event_store import record_event
        from database.user_store import update_user_location, upsert_user

        profile = upsert_user("google-reader", "reader@example.com")
        update_user_location(profile["user_id"], "PK", "Lahore")
        actor = user_context(profile["user_id"], "reader@example.com")
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
        record_event(
            kind="llm",
            actor_type="user",
            actor_id=profile["user_id"],
            route="/chat",
            provider="groq",
            category="rate_limit",
            message="groq rate limited",
        )

        body = admin_overview()
        providers = {row["provider"]: row["count"] for row in body["providers"]}
        self.assertGreaterEqual(providers.get("groq", 0), 1)
        self.assertTrue(any(item["provider"] == "groq" for item in body["answers"]))
        self.assertFalse(any(event["kind"] == "answer" for event in body["events"]))
        self.assertTrue(any(event["kind"] == "llm" for event in body["events"]))
        self.assertTrue(
            any(item["category"] == "not_in_document" for item in body["unanswered"])
        )
        person = next(row for row in body["people"] if row["email"] == "reader@example.com")
        self.assertEqual(person["country"], "PK")
        self.assertEqual(person["region"], "Lahore")
        self.assertGreaterEqual(person["answers"], 1)
        self.assertGreaterEqual(person["unanswered"], 1)
        self.assertTrue(any(place["country"] == "PK" for place in body["places"]))
        self.assertGreaterEqual(body["totals"]["errors_recent"], 1)
