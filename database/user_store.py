"""
Signed-in user profiles.

The identity provider owns authentication; this table maps its subject
claim to a stable internal user_id so switching providers does not rewrite
ownership rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from database.db import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_user(row) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "user_id": row[0],
        "auth_subject": row[1],
        "email": row[2],
        "created_at": row[3],
        "last_seen_at": row[4] if len(row) > 4 else None,
    }


def upsert_user(auth_subject: str, email: str | None = None) -> dict[str, Any]:
    """Return the profile for this identity, creating it on first sign-in."""
    now = _now()
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO users (user_id, auth_subject, email, created_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(auth_subject) DO UPDATE SET
            email = COALESCE(excluded.email, users.email),
            last_seen_at = excluded.last_seen_at
        """,
        (str(uuid.uuid4()), auth_subject, email, now, now),
    )
    connection.commit()
    cursor.execute(
        """
        SELECT user_id, auth_subject, email, created_at, last_seen_at
        FROM users
        WHERE auth_subject = ?
        """,
        (auth_subject,),
    )
    row = cursor.fetchone()
    connection.close()
    return _row_to_user(row)


def get_user(user_id: str) -> dict[str, Any] | None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT user_id, auth_subject, email, created_at, last_seen_at
        FROM users
        WHERE user_id = ?
        """,
        (user_id,),
    )
    row = cursor.fetchone()
    connection.close()
    return _row_to_user(row)


def list_users() -> list[dict[str, Any]]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT user_id, auth_subject, email, created_at, last_seen_at
        FROM users
        ORDER BY last_seen_at DESC, created_at DESC
        """
    )
    rows = cursor.fetchall()
    connection.close()
    users: list[dict[str, Any]] = []
    for row in rows:
        user = _row_to_user(row)
        if user:
            users.append(user)
    return users
