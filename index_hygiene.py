"""
Index hygiene and corpus isolation.

Live retrieval may only search documents that exist in SQLite with status
`ready`. Deletes and re-indexes must purge Chroma, BM25, evidence sidecars,
and on-disk PDFs so orphan chunks cannot leak into library answers.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import chromadb

from bm25_index import bm25_index
from config import CHROMA_DB_PATH, COLLECTION_NAME, DATA_DIR
from database.document_store import (
    count_documents_with_filename,
    delete_document,
    get_document,
    list_active_index_document_ids,
    list_ready_document_ids,
)
from database.evidence_store import delete_for_document
from document_paths import stored_pdf_path
from modes import MODE_SUPER_FOCUSED, normalize_mode

logger = logging.getLogger(__name__)

# Chroma $or filters become expensive/unreliable beyond this many ids.
_CHROMA_WHERE_ID_LIMIT = 32


def live_searchable_document_ids() -> list[str]:
    """Registry of documents retrieval is allowed to search."""
    return list_ready_document_ids()


def resolve_retrieval_scope(
    mode: str | None,
    document_ids: list[str] | None,
) -> tuple[list[str], bool]:
    """
    Return (scoped_ids, abort_without_search).

    abort_without_search is True only for Super Focused when no ready
    document is selected — callers must not search the rest of the corpus.

    Normal mode always returns an explicit list (possibly empty). Empty
    means search nothing, never "all of Chroma".
    """
    live = set(live_searchable_document_ids())
    requested = [doc_id for doc_id in (document_ids or []) if doc_id]
    normalized = normalize_mode(mode)

    if normalized == MODE_SUPER_FOCUSED:
        if not requested:
            return [], True
        selected = requested[0]
        if selected not in live:
            return [], True
        return [selected], False

    if requested:
        return [doc_id for doc_id in requested if doc_id in live], False
    return [doc_id for doc_id in live_searchable_document_ids() if doc_id in live], False


def chroma_where_for_document_ids(document_ids: list[str] | None) -> dict[str, Any] | None:
    """
    Chroma where clause, or None to skip the server-side filter.

    Empty list is handled by callers (no query). Large id sets skip the
    where clause and are post-filtered instead.
    """
    if not document_ids:
        return None
    if len(document_ids) > _CHROMA_WHERE_ID_LIMIT:
        return None
    if len(document_ids) == 1:
        return {"document_id": document_ids[0]}
    return {"$or": [{"document_id": doc_id} for doc_id in document_ids]}


def filter_hits_to_documents(
    hits: list[dict[str, Any]],
    document_ids: list[str] | None,
) -> list[dict[str, Any]]:
    """Drop candidates whose document_id is outside the allowed set."""
    if document_ids is None:
        return hits
    allowed = set(document_ids)
    kept: list[dict[str, Any]] = []
    for hit in hits:
        meta = hit.get("metadata") or {}
        if meta.get("document_id") in allowed:
            kept.append(hit)
    return kept


def _collection():
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    return client.get_or_create_collection(name=COLLECTION_NAME)


def purge_chroma_document(document_id: str, collection=None) -> int:
    """Delete every Chroma chunk for one document. Returns deleted id count."""
    if not document_id:
        return 0
    try:
        target = collection if collection is not None else _collection()
    except Exception:
        logger.exception("purge_chroma_document: cannot open collection")
        return 0

    ids_to_delete: list[str] = []
    try:
        payload = target.get(include=["metadatas"])
        for chunk_id, meta in zip(payload.get("ids") or [], payload.get("metadatas") or []):
            row = meta or {}
            if row.get("document_id") == document_id and chunk_id:
                ids_to_delete.append(str(chunk_id))
    except Exception:
        logger.exception(
            "purge_chroma_document: listing failed document_id=%s",
            document_id,
        )

    deleted = 0
    if ids_to_delete:
        try:
            target.delete(ids=ids_to_delete)
            deleted = len(ids_to_delete)
        except Exception:
            logger.exception(
                "purge_chroma_document: id delete failed document_id=%s",
                document_id,
            )
    try:
        target.delete(where={"document_id": document_id})
    except Exception:
        pass

    if deleted:
        logger.info(
            "purge_chroma_document document_id=%s deleted=%s",
            document_id,
            deleted,
        )
    return deleted


def delete_document_pdf_files(
    document_id: str,
    filename: str | None = None,
) -> list[str]:
    """Remove the id-keyed PDF and a legacy filename copy if unused."""
    removed: list[str] = []
    id_path = stored_pdf_path(document_id, must_exist=True)
    if id_path and os.path.isfile(id_path):
        try:
            os.remove(id_path)
            removed.append(id_path)
        except OSError:
            logger.exception("delete_document_pdf_files: cannot remove %s", id_path)

    name = (filename or "").strip()
    if name and count_documents_with_filename(name, exclude_document_id=document_id) == 0:
        data_root = os.path.abspath(DATA_DIR)
        os.makedirs(data_root, exist_ok=True)
        candidate = os.path.abspath(os.path.join(data_root, name))
        try:
            common = os.path.commonpath([data_root, candidate])
        except ValueError:
            common = ""
        if common == data_root and os.path.isfile(candidate) and candidate not in removed:
            try:
                os.remove(candidate)
                removed.append(candidate)
            except OSError:
                logger.exception(
                    "delete_document_pdf_files: cannot remove legacy %s",
                    candidate,
                )
    return removed


def purge_document_index(
    document_id: str,
    *,
    filename: str | None = None,
    delete_files: bool = True,
) -> dict[str, Any]:
    """
    Full index-side purge for one document (Chroma, evidence, BM25, files).

    Does not delete the SQLite documents row — callers do that when needed.
    """
    chroma_deleted = purge_chroma_document(document_id)
    try:
        delete_for_document(document_id)
    except Exception:
        logger.exception("purge_document_index: evidence delete failed document_id=%s", document_id)
    files: list[str] = []
    if delete_files:
        files = delete_document_pdf_files(document_id, filename)
    bm25_index.invalidate()
    return {
        "document_id": document_id,
        "chroma_deleted": chroma_deleted,
        "files_removed": files,
    }


def remove_document_completely(document_id: str) -> bool:
    """Public delete: purge indexes + files + SQLite registry row."""
    if not document_id:
        return False
    record = get_document(document_id)
    filename = (record or {}).get("filename") if record else None
    result = purge_document_index(document_id, filename=filename, delete_files=True)
    sqlite_deleted = delete_document(document_id) if record else False
    removed = bool(record) or int(result.get("chroma_deleted") or 0) > 0
    logger.info(
        "remove_document_completely document_id=%s sqlite=%s chroma=%s",
        document_id,
        sqlite_deleted,
        result.get("chroma_deleted"),
    )
    return removed


def reconcile_index() -> dict[str, Any]:
    """
    Drop Chroma/evidence rows that do not belong to an active registry document.

    Active = ready or currently indexing. Failed/missing IDs are orphans.
    """
    keep = set(list_active_index_document_ids())
    orphan_ids: set[str] = set()
    orphan_documents: set[str] = set()
    chroma_deleted = 0
    payload: dict[str, Any] = {"ids": [], "metadatas": []}
    collection = None

    try:
        collection = _collection()
        payload = collection.get(include=["metadatas"])
        for chunk_id, meta in zip(payload.get("ids") or [], payload.get("metadatas") or []):
            row = meta or {}
            doc_id = str(row.get("document_id") or "")
            if doc_id and doc_id in keep:
                continue
            if chunk_id:
                orphan_ids.add(str(chunk_id))
            if doc_id:
                orphan_documents.add(doc_id)
    except Exception:
        logger.exception("reconcile_index: cannot list Chroma corpus")
        collection = None

    if orphan_ids and collection is not None:
        try:
            collection.delete(ids=list(orphan_ids))
            chroma_deleted = len(orphan_ids)
        except Exception:
            logger.exception("reconcile_index: chroma id delete failed")
            chroma_deleted = 0
            for doc_id in orphan_documents:
                chroma_deleted += purge_chroma_document(doc_id)

    evidence_purged = 0
    for doc_id in orphan_documents:
        try:
            delete_for_document(doc_id)
            evidence_purged += 1
        except Exception:
            logger.exception("reconcile_index: evidence purge failed document_id=%s", doc_id)

    if chroma_deleted or evidence_purged:
        bm25_index.invalidate()

    logger.info(
        "reconcile_index chroma_deleted=%s orphan_documents=%s evidence_purged=%s keep=%s",
        chroma_deleted,
        len(orphan_documents),
        evidence_purged,
        len(keep),
    )
    return {
        "chroma_deleted": chroma_deleted,
        "orphan_documents": sorted(orphan_documents),
        "evidence_purged": evidence_purged,
        "kept_documents": len(keep),
    }
