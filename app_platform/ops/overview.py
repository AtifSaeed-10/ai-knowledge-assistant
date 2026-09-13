"""Assemble the operator dashboard payload."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app_platform.ops.azure import azure_status
from database.admin_store import groq_status, list_labeled_events, list_people, list_uploads, totals


def admin_overview() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=7)).isoformat()
    return {
        "generated_at": now.isoformat(),
        "totals": totals(events_since=since, today=now.strftime("%Y-%m-%d")),
        "people": list_people(),
        "uploads": list_uploads(),
        "events": list_labeled_events(),
        "groq": groq_status(),
        "azure": azure_status(),
    }
