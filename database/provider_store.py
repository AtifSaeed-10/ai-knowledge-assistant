"""Latest Groq (and future provider) rate-limit snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from database.db import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def record_provider_call(
    provider: str,
    limits: dict[str, Any] | None,
    tokens: int = 0,
    error: str | None = None,
) -> None:
    """Merge one API call into the rolling snapshot for this provider."""
    today = _today()
    limits = limits or {}
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT tokens_used_today, requests_today, usage_day, last_error
        FROM provider_snapshots
        WHERE provider = ?
        """,
        (provider,),
    )
    row = cursor.fetchone()
    if row and row[2] == today:
        tokens_today = int(row[0] or 0) + max(0, int(tokens or 0))
        requests_today = int(row[1] or 0) + 1
        last_error = error if error else row[3]
    else:
        tokens_today = max(0, int(tokens or 0))
        requests_today = 1
        last_error = error

    cursor.execute(
        """
        INSERT INTO provider_snapshots (
            provider, updated_at,
            remaining_requests, limit_requests,
            remaining_tokens, limit_tokens,
            reset_requests, reset_tokens,
            tokens_used_today, requests_today, usage_day, last_error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(provider) DO UPDATE SET
            updated_at = excluded.updated_at,
            remaining_requests = COALESCE(
                excluded.remaining_requests, provider_snapshots.remaining_requests
            ),
            limit_requests = COALESCE(
                excluded.limit_requests, provider_snapshots.limit_requests
            ),
            remaining_tokens = COALESCE(
                excluded.remaining_tokens, provider_snapshots.remaining_tokens
            ),
            limit_tokens = COALESCE(
                excluded.limit_tokens, provider_snapshots.limit_tokens
            ),
            reset_requests = COALESCE(
                excluded.reset_requests, provider_snapshots.reset_requests
            ),
            reset_tokens = COALESCE(
                excluded.reset_tokens, provider_snapshots.reset_tokens
            ),
            tokens_used_today = excluded.tokens_used_today,
            requests_today = excluded.requests_today,
            usage_day = excluded.usage_day,
            last_error = excluded.last_error
        """,
        (
            provider,
            _now(),
            limits.get("remaining_requests"),
            limits.get("limit_requests"),
            limits.get("remaining_tokens"),
            limits.get("limit_tokens"),
            limits.get("reset_requests"),
            limits.get("reset_tokens"),
            tokens_today,
            requests_today,
            today,
            last_error,
        ),
    )
    connection.commit()
    connection.close()


def get_snapshot(provider: str) -> dict[str, Any] | None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            provider, updated_at,
            remaining_requests, limit_requests,
            remaining_tokens, limit_tokens,
            reset_requests, reset_tokens,
            tokens_used_today, requests_today, usage_day, last_error
        FROM provider_snapshots
        WHERE provider = ?
        """,
        (provider,),
    )
    row = cursor.fetchone()
    connection.close()
    if not row:
        return None
    today = _today()
    same_day = row[10] == today
    return {
        "provider": row[0],
        "updated_at": row[1],
        "remaining_requests": row[2],
        "limit_requests": row[3],
        "remaining_tokens": row[4],
        "limit_tokens": row[5],
        "reset_requests": row[6],
        "reset_tokens": row[7],
        "tokens_used_today": int(row[8] or 0) if same_day else 0,
        "requests_today": int(row[9] or 0) if same_day else 0,
        "usage_day": row[10],
        "last_error": row[11],
    }
