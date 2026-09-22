"""Assemble the operator dashboard payload."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app_platform.ops.azure import azure_status
from database.admin_store import (
    groq_status,
    list_labeled_answers,
    list_labeled_events,
    list_people,
    list_uploads,
    places_summary,
    totals,
    unanswered_breakdown,
)
from database.event_store import answer_provider_breakdown


def admin_overview() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = (now - timedelta(days=7)).isoformat()
    people = list_people()
    return {
        "generated_at": now.isoformat(),
        "totals": totals(events_since=since, today=now.strftime("%Y-%m-%d")),
        "people": people,
        "places": places_summary(people),
        "unanswered": unanswered_breakdown(),
        "providers": answer_provider_breakdown(),
        "answers": list_labeled_answers(),
        "uploads": list_uploads(),
        "events": list_labeled_events(),
        "groq": groq_status(),
        "azure": azure_status(),
    }
