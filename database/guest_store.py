"""Guest trial sessions and their usage counters."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from database.db import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_guest_session(session_id: str) -> dict[str, Any]:
    """Create the trial row on first sight; refresh last_seen otherwise."""
    now = _now()
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO guest_sessions (
            session_id, created_at, last_seen_at, pdf_count, question_count
        )
        VALUES (?, ?, ?, 0, 0)
        ON CONFLICT(session_id) DO UPDATE SET last_seen_at = excluded.last_seen_at
        """,
        (session_id, now, now),
    )
    connection.commit()
    cursor.execute(
        """
        SELECT session_id, created_at, pdf_count, question_count, migrated_to_user_id
        FROM guest_sessions
        WHERE session_id = ?
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    connection.close()
    return {
        "session_id": row[0],
        "created_at": row[1],
        "pdf_count": int(row[2] or 0),
        "question_count": int(row[3] or 0),
        "migrated_to_user_id": row[4],
    }


def get_guest_session(session_id: str) -> dict[str, Any] | None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT session_id, created_at, pdf_count, question_count, migrated_to_user_id
        FROM guest_sessions
        WHERE session_id = ?
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    connection.close()
    if not row:
        return None
    return {
        "session_id": row[0],
        "created_at": row[1],
        "pdf_count": int(row[2] or 0),
        "question_count": int(row[3] or 0),
        "migrated_to_user_id": row[4],
    }


def increment_guest_pdf_count(session_id: str) -> None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE guest_sessions
        SET pdf_count = pdf_count + 1, last_seen_at = ?
        WHERE session_id = ?
        """,
        (_now(), session_id),
    )
    connection.commit()
    connection.close()


def increment_guest_question_count(session_id: str) -> None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE guest_sessions
        SET question_count = question_count + 1, last_seen_at = ?
        WHERE session_id = ?
        """,
        (_now(), session_id),
    )
    connection.commit()
    connection.close()


def mark_guest_migrated(session_id: str, user_id: str) -> None:
    """Record that this trial was claimed, so it cannot be claimed twice."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE guest_sessions
        SET migrated_to_user_id = ?, last_seen_at = ?
        WHERE session_id = ?
        """,
        (user_id, _now(), session_id),
    )
    connection.commit()
    connection.close()
