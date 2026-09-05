"""
Row-level access control.

Knowing a UUID must not be enough to read someone else's document or chat.
Legacy rows created before ownership existed have a NULL owner and stay
readable, so upgrading an existing install does not orphan data.
"""

from __future__ import annotations

from fastapi import HTTPException

from app_platform import errors
from app_platform.auth.context import RequestContext
from database.document_store import get_document, owners_for_documents
from memory.store import conversation_owner


def _owns(context: RequestContext, owner_type, owner_id) -> bool:
    if not owner_type and not owner_id:
        # Pre-ownership row: shared, as it was before this layer existed.
        return True
    return owner_type == context.actor_type and owner_id == context.actor_id


def owns_document(context: RequestContext, document_id: str) -> bool:
    record = get_document(document_id)
    if not record:
        return False
    return _owns(context, record.get("owner_type"), record.get("owner_id"))


def assert_document_owner(context: RequestContext, document_id: str) -> dict:
    """Return the document record, or raise 404 if absent / 403 if foreign."""
    record = get_document(document_id)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")
    if not _owns(context, record.get("owner_type"), record.get("owner_id")):
        raise errors.forbidden("Document not found.")
    return record


def assert_conversation_owner(context: RequestContext, conversation_id: str) -> None:
    owner = conversation_owner(conversation_id)
    if owner is None:
        # Conversation does not exist yet; creation binds it to this actor.
        return
    if not _owns(context, owner[0], owner[1]):
        raise errors.forbidden("Conversation not found.")


def visible_document_ids(
    context: RequestContext,
    document_ids: list[str] | None,
) -> list[str]:
    """
    Drop ids belonging to another actor, preserving order.

    Applied both to what the client asked for and to whatever the retrieval
    scope resolved, so no foreign document can reach the RAG pipeline.
    """
    ids = [doc_id for doc_id in (document_ids or []) if doc_id]
    if not ids:
        return []
    owners = owners_for_documents(ids)
    kept: list[str] = []
    for doc_id in ids:
        owner = owners.get(doc_id)
        # Unknown ids are left in place; retrieval simply finds nothing.
        if owner is None or _owns(context, owner[0], owner[1]):
            kept.append(doc_id)
    return kept
