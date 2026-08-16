from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from database.db import get_connection, init_db

init_db()

DEFAULT_TITLE = "New conversation"
TITLE_MAX_LEN = 64


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _title_from_content(content: str) -> str:
    compact = " ".join((content or "").split())
    if not compact:
        return DEFAULT_TITLE
    if len(compact) <= TITLE_MAX_LEN:
        return compact
    return compact[: TITLE_MAX_LEN - 1].rstrip() + "…"


def _parse_citations(raw: str | None) -> list[dict[str, Any]] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, list):
        return parsed
    return None


def ensure_conversation(
    conversation_id: str,
    title: str | None = None,
) -> dict[str, Any]:
    """Create a conversation row if missing; return its record."""
    cid = (conversation_id or "").strip() or new_conversation_id()
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT conversation_id, title, created_at, updated_at
        FROM conversations
        WHERE conversation_id = ?
        """,
        (cid,),
    )
    row = cursor.fetchone()
    if row:
        connection.close()
        return {
            "conversation_id": row[0],
            "title": row[1],
            "created_at": row[2],
            "updated_at": row[3],
        }

    created = _now()
    resolved_title = (title or "").strip() or DEFAULT_TITLE
    cursor.execute(
        """
        INSERT INTO conversations (
            conversation_id, title, created_at, updated_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (cid, resolved_title, created, created),
    )
    connection.commit()
    connection.close()
    return {
        "conversation_id": cid,
        "title": resolved_title,
        "created_at": created,
        "updated_at": created,
    }


def new_conversation_id() -> str:
    return f"conv-{uuid.uuid4().hex[:12]}"


def create_conversation(title: str | None = None) -> dict[str, Any]:
    return ensure_conversation(new_conversation_id(), title=title)


def list_conversations() -> list[dict[str, Any]]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            c.conversation_id,
            c.title,
            c.created_at,
            c.updated_at,
            (
                SELECT m.content
                FROM messages m
                WHERE m.conversation_id = c.conversation_id
                  AND m.role = 'user'
                ORDER BY m.id ASC
                LIMIT 1
            ) AS preview
        FROM conversations c
        ORDER BY c.updated_at DESC
        """
    )
    rows = cursor.fetchall()
    connection.close()
    return [
        {
            "conversation_id": row[0],
            "title": row[1],
            "created_at": row[2],
            "updated_at": row[3],
            "preview": row[4] or "",
        }
        for row in rows
    ]


def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT conversation_id, title, created_at, updated_at
        FROM conversations
        WHERE conversation_id = ?
        """,
        (conversation_id,),
    )
    row = cursor.fetchone()
    if not row:
        connection.close()
        return None

    cursor.execute(
        """
        SELECT id, role, content, citations, created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id ASC
        """,
        (conversation_id,),
    )
    messages = []
    for item in cursor.fetchall():
        messages.append(
            {
                "id": item[0],
                "role": item[1],
                "content": item[2],
                "citations": _parse_citations(item[3]),
                "created_at": item[4],
            }
        )
    connection.close()
    return {
        "conversation_id": row[0],
        "title": row[1],
        "created_at": row[2],
        "updated_at": row[3],
        "messages": messages,
    }


def rename_conversation(conversation_id: str, title: str) -> dict[str, Any] | None:
    compact = " ".join((title or "").split())
    if not compact:
        compact = DEFAULT_TITLE
    compact = compact[:TITLE_MAX_LEN]
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE conversations
        SET title = ?, updated_at = ?
        WHERE conversation_id = ?
        """,
        (compact, _now(), conversation_id),
    )
    updated = cursor.rowcount
    connection.commit()
    connection.close()
    if updated <= 0:
        return None
    record = get_conversation(conversation_id)
    return record


def save_message(
    conversation_id: str,
    role: str,
    content: str,
    citations: list[dict[str, Any]] | None = None,
):
    """
    Store one message. Creates the conversation if needed.
    """
    ensure_conversation(conversation_id)
    connection = get_connection()
    cursor = connection.cursor()
    created = _now()
    citations_json = json.dumps(citations) if citations else None
    cursor.execute(
        """
        INSERT INTO messages (
            conversation_id, role, content, citations, created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (conversation_id, role, content, citations_json, created),
    )

    if role == "user":
        cursor.execute(
            """
            SELECT title FROM conversations WHERE conversation_id = ?
            """,
            (conversation_id,),
        )
        row = cursor.fetchone()
        current_title = row[0] if row else DEFAULT_TITLE
        if current_title == DEFAULT_TITLE:
            cursor.execute(
                """
                UPDATE conversations
                SET title = ?, updated_at = ?
                WHERE conversation_id = ?
                """,
                (_title_from_content(content), created, conversation_id),
            )
        else:
            cursor.execute(
                """
                UPDATE conversations
                SET updated_at = ?
                WHERE conversation_id = ?
                """,
                (created, conversation_id),
            )
    else:
        cursor.execute(
            """
            UPDATE conversations
            SET updated_at = ?
            WHERE conversation_id = ?
            """,
            (created, conversation_id),
        )

    connection.commit()
    connection.close()


def load_conversation(
    conversation_id: str
) -> list[dict]:
    """
    Return conversation messages for the rewriter / RAG history.
    """
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT role, content
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id ASC
        """,
        (conversation_id,),
    )
    rows = cursor.fetchall()
    connection.close()
    return [
        {
            "role": row[0],
            "content": row[1],
        }
        for row in rows
    ]


def delete_conversation(
    conversation_id: str
):
    """
    Delete conversation memory.
    """
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM messages WHERE conversation_id = ?",
        (conversation_id,),
    )
    cursor.execute(
        "DELETE FROM conversations WHERE conversation_id = ?",
        (conversation_id,),
    )
    connection.commit()
    connection.close()


def delete_last_assistant_message(conversation_id: str) -> bool:
    """Remove the most recent assistant message if it is last. Used by regenerate."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT id, role
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (conversation_id,),
    )
    row = cursor.fetchone()
    if not row or row[1] != "assistant":
        connection.close()
        return False
    cursor.execute("DELETE FROM messages WHERE id = ?", (row[0],))
    cursor.execute(
        """
        UPDATE conversations
        SET updated_at = ?
        WHERE conversation_id = ?
        """,
        (_now(), conversation_id),
    )
    connection.commit()
    connection.close()
    return True
