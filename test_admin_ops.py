"""Unit checks for Groq header parsing and Azure credit estimates."""

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
