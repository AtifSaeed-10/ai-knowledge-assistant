"""Cross-actor reads for the operator dashboard. Never used by product routes."""

from __future__ import annotations

from typing import Any

from database.db import get_connection
from database.event_store import count_events_since, list_recent_events
from database.guest_store import list_guest_sessions
from database.provider_store import get_snapshot
from database.usage_store import current_period
from database.user_store import list_users


def _counts_by_owner(table: str) -> dict[tuple[str, str], int]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        f"""
        SELECT owner_type, owner_id, COUNT(*)
        FROM {table}
        WHERE owner_type IS NOT NULL AND owner_id IS NOT NULL
        GROUP BY owner_type, owner_id
        """
    )
    rows = cursor.fetchall()
    connection.close()
    return {(row[0], row[1]): int(row[2] or 0) for row in rows}


def _document_stats_by_owner() -> dict[tuple[str, str], dict[str, int]]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            owner_type,
            owner_id,
            COUNT(*),
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END),
            SUM(CASE WHEN status = 'ready' THEN 1 ELSE 0 END)
        FROM documents
        WHERE owner_type IS NOT NULL AND owner_id IS NOT NULL
        GROUP BY owner_type, owner_id
        """
    )
    rows = cursor.fetchall()
    connection.close()
    stats: dict[tuple[str, str], dict[str, int]] = {}
    for row in rows:
        stats[(row[0], row[1])] = {
            "pdfs": int(row[2] or 0),
            "failed": int(row[3] or 0),
            "ready": int(row[4] or 0),
        }
    return stats


def _questions_this_month() -> dict[str, int]:
    period = current_period()
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT actor_id, question_count
        FROM usage_counters
        WHERE actor_type = 'user' AND period = ?
        """,
        (period,),
    )
    rows = cursor.fetchall()
    connection.close()
    return {row[0]: int(row[1] or 0) for row in rows}


def _user_email_map() -> dict[str, str | None]:
    return {user["user_id"]: user.get("email") for user in list_users()}


def list_people() -> list[dict[str, Any]]:
    docs = _document_stats_by_owner()
    chats = _counts_by_owner("conversations")
    monthly = _questions_this_month()
    emails = _user_email_map()
    people: list[dict[str, Any]] = []

    for user in list_users():
        key = ("user", user["user_id"])
        stat = docs.get(key, {"pdfs": 0, "failed": 0, "ready": 0})
        people.append(
            {
                "actor_type": "user",
                "actor_id": user["user_id"],
                "label": user.get("email") or "Signed-in user",
                "email": user.get("email"),
                "created_at": user.get("created_at"),
                "last_seen_at": user.get("last_seen_at"),
                "pdfs": stat["pdfs"],
                "failed_pdfs": stat["failed"],
                "ready_pdfs": stat["ready"],
                "questions": monthly.get(user["user_id"], 0),
                "chats": chats.get(key, 0),
                "migrated_to": None,
            }
        )

    for guest in list_guest_sessions():
        key = ("guest", guest["session_id"])
        stat = docs.get(key, {"pdfs": 0, "failed": 0, "ready": 0})
        migrated_id = guest.get("migrated_to_user_id")
        people.append(
            {
                "actor_type": "guest",
                "actor_id": guest["session_id"],
                "label": _guest_label(guest["session_id"]),
                "email": None,
                "created_at": guest.get("created_at"),
                "last_seen_at": guest.get("last_seen_at"),
                "pdfs": stat["pdfs"],
                "failed_pdfs": stat["failed"],
                "ready_pdfs": stat["ready"],
                "questions": int(guest.get("question_count") or 0),
                "chats": chats.get(key, 0),
                "migrated_to": emails.get(migrated_id) if migrated_id else None,
            }
        )

    people.sort(key=lambda row: row.get("last_seen_at") or "", reverse=True)
    return people


def _guest_label(session_id: str) -> str:
    tail = (session_id or "")[-8:]
    return f"Guest · {tail}" if tail else "Guest"


def list_uploads(limit: int = 100) -> list[dict[str, Any]]:
    emails = _user_email_map()
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            document_id, filename, upload_time, total_pages, total_chunks,
            status, index_error, owner_type, owner_id
        FROM documents
        ORDER BY upload_time DESC
        LIMIT ?
        """,
        (max(1, min(limit, 300)),),
    )
    rows = cursor.fetchall()
    connection.close()

    uploads = []
    for row in rows:
        owner_type, owner_id = row[7], row[8]
        if owner_type == "user":
            owner_label = emails.get(owner_id) or "Signed-in user"
        elif owner_type == "guest":
            owner_label = _guest_label(owner_id or "")
        else:
            owner_label = "Unknown"
        uploads.append(
            {
                "document_id": row[0],
                "filename": row[1],
                "uploaded_at": row[2],
                "total_pages": row[3],
                "total_chunks": row[4],
                "status": row[5],
                "index_error": row[6],
                "owner_type": owner_type,
                "owner_label": owner_label,
            }
        )
    return uploads


def list_labeled_events(limit: int = 50) -> list[dict[str, Any]]:
    emails = _user_email_map()
    events = []
    for event in list_recent_events(limit):
        actor_type = event.get("actor_type")
        actor_id = event.get("actor_id")
        if actor_type == "user":
            label = emails.get(actor_id) or "Signed-in user"
        elif actor_type == "guest" and actor_id:
            label = _guest_label(actor_id)
        else:
            label = "System"
        events.append({**event, "actor_label": label})
    return events


def totals(*, events_since: str, today: str) -> dict[str, int]:
    people_docs = _document_stats_by_owner()
    monthly = _questions_this_month()
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    users = int((cursor.fetchone() or [0])[0] or 0)
    cursor.execute("SELECT COUNT(*) FROM guest_sessions")
    guests = int((cursor.fetchone() or [0])[0] or 0)
    cursor.execute("SELECT COUNT(*) FROM documents")
    pdfs = int((cursor.fetchone() or [0])[0] or 0)
    cursor.execute("SELECT COUNT(*) FROM documents WHERE status = 'failed'")
    failed = int((cursor.fetchone() or [0])[0] or 0)
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM messages
        WHERE role = 'user' AND created_at >= ?
        """,
        (today,),
    )
    questions_today = int((cursor.fetchone() or [0])[0] or 0)
    connection.close()

    pdfs_from_people = sum(stat["pdfs"] for stat in people_docs.values())
    return {
        "signed_in_users": users,
        "guest_sessions": guests,
        "pdfs": pdfs or pdfs_from_people,
        "failed_pdfs": failed,
        "questions_this_month": sum(monthly.values()),
        "questions_today": questions_today,
        "errors_recent": count_events_since(events_since),
    }


def groq_status() -> dict[str, Any]:
    snap = get_snapshot("groq")
    if not snap:
        return {
            "configured": False,
            "updated_at": None,
            "remaining_requests": None,
            "limit_requests": None,
            "remaining_tokens": None,
            "limit_tokens": None,
            "reset_requests": None,
            "reset_tokens": None,
            "tokens_used_today": 0,
            "requests_today": 0,
            "last_error": None,
        }
    return {
        "configured": True,
        "updated_at": snap["updated_at"],
        "remaining_requests": snap["remaining_requests"],
        "limit_requests": snap["limit_requests"],
        "remaining_tokens": snap["remaining_tokens"],
        "limit_tokens": snap["limit_tokens"],
        "reset_requests": snap["reset_requests"],
        "reset_tokens": snap["reset_tokens"],
        "tokens_used_today": snap["tokens_used_today"],
        "requests_today": snap["requests_today"],
        "last_error": snap["last_error"],
    }
