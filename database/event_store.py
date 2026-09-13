"""Append-only operator events (errors and quota blocks)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from database.db import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_event(
    *,
    kind: str,
    actor_type: str | None = None,
    actor_id: str | None = None,
    route: str | None = None,
    provider: str | None = None,
    category: str | None = None,
    status_code: int | None = None,
    message: str | None = None,
    document_id: str | None = None,
) -> None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO app_events (
            event_id, created_at, actor_type, actor_id, route,
            kind, provider, category, status_code, message, document_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            _now(),
            actor_type,
            actor_id,
            route,
            kind,
            provider,
            category,
            status_code,
            message,
            document_id,
        ),
    )
    connection.commit()
    connection.close()


def list_recent_events(limit: int = 50) -> list[dict[str, Any]]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            event_id, created_at, actor_type, actor_id, route,
            kind, provider, category, status_code, message, document_id
        FROM app_events
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (max(1, min(limit, 200)),),
    )
    rows = cursor.fetchall()
    connection.close()
    return [
        {
            "event_id": row[0],
            "created_at": row[1],
            "actor_type": row[2],
            "actor_id": row[3],
            "route": row[4],
            "kind": row[5],
            "provider": row[6],
            "category": row[7],
            "status_code": row[8],
            "message": row[9],
            "document_id": row[10],
        }
        for row in rows
    ]


def count_events_since(since_iso: str) -> int:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM app_events
        WHERE created_at >= ?
        """,
        (since_iso,),
    )
    row = cursor.fetchone()
    connection.close()
    return int(row[0] or 0) if row else 0
