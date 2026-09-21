"""Period-scoped question counters shared by both actor tiers."""

from __future__ import annotations

from datetime import datetime, timezone

from database.db import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_period() -> str:
    """Calendar month key, e.g. 2026-09."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


def get_question_count(actor_type: str, actor_id: str, period: str) -> int:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT question_count
        FROM usage_counters
        WHERE actor_type = ? AND actor_id = ? AND period = ?
        """,
        (actor_type, actor_id, period),
    )
    row = cursor.fetchone()
    connection.close()
    return int(row[0] or 0) if row else 0


def increment_question_count(actor_type: str, actor_id: str, period: str) -> None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO usage_counters (
            actor_type, actor_id, period, question_count, updated_at
        )
        VALUES (?, ?, ?, 1, ?)
        ON CONFLICT(actor_type, actor_id, period) DO UPDATE SET
            question_count = usage_counters.question_count + 1,
            updated_at = excluded.updated_at
        """,
        (actor_type, actor_id, period, _now()),
    )
    connection.commit()
    connection.close()


def get_web_question_count(actor_type: str, actor_id: str, period: str) -> int:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT web_question_count
        FROM usage_counters
        WHERE actor_type = ? AND actor_id = ? AND period = ?
        """,
        (actor_type, actor_id, period),
    )
    row = cursor.fetchone()
    connection.close()
    if not row:
        return 0
    return int(row[0] or 0)


def increment_web_question_count(actor_type: str, actor_id: str, period: str) -> None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO usage_counters (
            actor_type, actor_id, period, question_count, web_question_count, updated_at
        )
        VALUES (?, ?, ?, 0, 1, ?)
        ON CONFLICT(actor_type, actor_id, period) DO UPDATE SET
            web_question_count = COALESCE(usage_counters.web_question_count, 0) + 1,
            updated_at = excluded.updated_at
        """,
        (actor_type, actor_id, period, _now()),
    )
    connection.commit()
    connection.close()
