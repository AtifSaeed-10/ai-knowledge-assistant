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


_ISSUE_KINDS = ("http", "quota", "llm", "index", "unanswered")


def list_recent_events(
    limit: int = 50,
    *,
    kinds: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    connection = get_connection()
    cursor = connection.cursor()
    selected = kinds if kinds is not None else _ISSUE_KINDS
    placeholders = ",".join("?" for _ in selected)
    cursor.execute(
        f"""
        SELECT
            event_id, created_at, actor_type, actor_id, route,
            kind, provider, category, status_code, message, document_id
        FROM app_events
        WHERE kind IN ({placeholders})
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (*selected, max(1, min(limit, 200))),
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
          AND kind != 'answer'
        """,
        (since_iso,),
    )
    row = cursor.fetchone()
    connection.close()
    return int(row[0] or 0) if row else 0


def event_counts_by_actor() -> dict[tuple[str, str], dict[str, int]]:
    """Per-actor error and unanswered counts for the operator people table."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT actor_type, actor_id, kind, COUNT(*)
        FROM app_events
        WHERE actor_type IS NOT NULL AND actor_id IS NOT NULL
        GROUP BY actor_type, actor_id, kind
        """
    )
    rows = cursor.fetchall()
    connection.close()
    counts: dict[tuple[str, str], dict[str, int]] = {}
    for actor_type, actor_id, kind, total in rows:
        key = (str(actor_type), str(actor_id))
        bucket = counts.setdefault(key, {"errors": 0, "unanswered": 0, "answers": 0})
        n = int(total or 0)
        if kind == "unanswered":
            bucket["unanswered"] += n
        elif kind == "answer":
            bucket["answers"] += n
        else:
            bucket["errors"] += n
    return counts


def answer_provider_breakdown() -> list[dict[str, Any]]:
    """How many grounded answers each LLM produced."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT COALESCE(provider, 'unknown'), COUNT(*), MAX(created_at)
        FROM app_events
        WHERE kind = 'answer'
        GROUP BY COALESCE(provider, 'unknown')
        ORDER BY COUNT(*) DESC
        """
    )
    rows = cursor.fetchall()
    connection.close()
    return [
        {
            "provider": str(provider),
            "count": int(total or 0),
            "last_at": last_at,
        }
        for provider, total, last_at in rows
    ]


def unanswered_breakdown(limit: int = 80) -> list[dict[str, Any]]:
    """Group recent couldn't-answer events by kind."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT category, COUNT(*), MAX(created_at)
        FROM app_events
        WHERE kind = 'unanswered'
        GROUP BY category
        ORDER BY COUNT(*) DESC
        """
    )
    grouped = cursor.fetchall()
    latest_by_category: dict[str, str | None] = {}
    cursor.execute(
        """
        SELECT category, message, created_at
        FROM app_events
        WHERE kind = 'unanswered'
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (max(1, min(limit, 200)),),
    )
    for category, message, created_at in cursor.fetchall():
        key = str(category or "not_in_document")
        if key not in latest_by_category:
            latest_by_category[key] = message
    connection.close()

    from app_platform.ops.unanswered import unanswered_label

    rows: list[dict[str, Any]] = []
    for category, total, last_at in grouped:
        key = str(category or "not_in_document")
        rows.append(
            {
                "category": key,
                "label": unanswered_label(key),
                "count": int(total or 0),
                "last_at": last_at,
                "last_question": latest_by_category.get(key),
            }
        )
    return rows
