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
        SELECT session_id, created_at, last_seen_at, pdf_count, question_count,
               migrated_to_user_id, country, region, web_question_count
        FROM guest_sessions
        WHERE session_id = ?
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    connection.close()
    return _row_to_guest(row)


def _row_to_guest(row) -> dict[str, Any]:
    return {
        "session_id": row[0],
        "created_at": row[1],
        "last_seen_at": row[2],
        "pdf_count": int(row[3] or 0),
        "question_count": int(row[4] or 0),
        "migrated_to_user_id": row[5],
        "country": row[6] if len(row) > 6 else None,
        "region": row[7] if len(row) > 7 else None,
        "web_question_count": int(row[8] or 0) if len(row) > 8 else 0,
    }


def get_guest_session(session_id: str) -> dict[str, Any] | None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT session_id, created_at, last_seen_at, pdf_count, question_count,
               migrated_to_user_id, country, region, web_question_count
        FROM guest_sessions
        WHERE session_id = ?
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    connection.close()
    if not row:
        return None
    return _row_to_guest(row)


def list_guest_sessions() -> list[dict[str, Any]]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT session_id, created_at, last_seen_at, pdf_count, question_count, migrated_to_user_id, country, region, web_question_count
        FROM guest_sessions
        ORDER BY last_seen_at DESC, created_at DESC
        """
    )
    rows = cursor.fetchall()
    connection.close()
    return [_row_to_guest(row) for row in rows]


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


def increment_guest_web_question_count(session_id: str) -> None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE guest_sessions
        SET web_question_count = COALESCE(web_question_count, 0) + 1,
            last_seen_at = ?
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


def update_guest_location(
    session_id: str,
    country: str | None,
    region: str | None,
) -> None:
    if not session_id or (not country and not region):
        return
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE guest_sessions
        SET
            country = COALESCE(?, country),
            region = COALESCE(?, region)
        WHERE session_id = ?
        """,
        (country or None, region or None, session_id),
    )
    connection.commit()
    connection.close()
