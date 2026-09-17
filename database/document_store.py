import sqlite3
import uuid
from datetime import datetime

from database.db import get_connection


def create_document(filename, owner_type=None, owner_id=None):

    document_id = str(uuid.uuid4())

    upload_time = datetime.now().isoformat()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO documents
        (
            document_id,
            filename,
            upload_time,
            total_pages,
            total_chunks,
            owner_type,
            owner_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            filename,
            upload_time,
            0,
            0,
            owner_type,
            owner_id
        )
    )

    connection.commit()
    connection.close()

    return document_id
    
def update_document_metadata(
    document_id,
    total_pages,
    total_chunks
):

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE documents
        SET
            total_pages = ?,
            total_chunks = ?
        WHERE document_id = ?
        """,
        (
            total_pages,
            total_chunks,
            document_id
        )
    )

    connection.commit()

    connection.close()

def document_to_dict(document):

    if not document:
        return None


    return {
        "document_id": document[0],
        "filename": document[1],
        "upload_time": document[2],
        "total_pages": document[3],
        "total_chunks": document[4],
        "status": document[5],
        "index_error": document[6] if len(document) > 6 else None,
        "owner_type": document[7] if len(document) > 7 else None,
        "owner_id": document[8] if len(document) > 8 else None,
        "index_updated_at": document[9] if len(document) > 9 else None,
    }


def count_documents_for_owner(owner_type: str, owner_id: str) -> int:
    """Documents this actor currently holds. Excludes failed uploads."""
    if not owner_type or not owner_id:
        return 0
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM documents
        WHERE owner_type = ? AND owner_id = ? AND status != 'failed'
        """,
        (owner_type, owner_id),
    )
    row = cursor.fetchone()
    connection.close()
    return int(row[0] or 0) if row else 0


def get_documents_for_owner(owner_type: str, owner_id: str) -> list:
    if not owner_type or not owner_id:
        return []
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT *
        FROM documents
        WHERE owner_type = ? AND owner_id = ?
        ORDER BY upload_time DESC
        """,
        (owner_type, owner_id),
    )
    rows = cursor.fetchall()
    connection.close()
    return [document_to_dict(row) for row in rows]


def list_ready_document_ids_for_owner(owner_type: str, owner_id: str) -> list:
    """Indexed document ids this actor is allowed to retrieve from."""
    if not owner_type or not owner_id:
        return []
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT document_id
        FROM documents
        WHERE status = 'ready' AND owner_type = ? AND owner_id = ?
        ORDER BY upload_time DESC
        """,
        (owner_type, owner_id),
    )
    rows = cursor.fetchall()
    connection.close()
    return [row[0] for row in rows if row and row[0]]


def owners_for_documents(document_ids: list) -> dict:
    """Map document_id -> (owner_type, owner_id) in one query."""
    ids = [doc_id for doc_id in (document_ids or []) if doc_id]
    if not ids:
        return {}
    connection = get_connection()
    cursor = connection.cursor()
    placeholders = ",".join("?" for _ in ids)
    cursor.execute(
        f"""
        SELECT document_id, owner_type, owner_id
        FROM documents
        WHERE document_id IN ({placeholders})
        """,
        ids,
    )
    rows = cursor.fetchall()
    connection.close()
    return {row[0]: (row[1], row[2]) for row in rows if row and row[0]}


def reassign_documents(
    from_owner_type: str,
    from_owner_id: str,
    to_owner_type: str,
    to_owner_id: str,
) -> int:
    """Move ownership of every document from one actor to another."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE documents
        SET owner_type = ?, owner_id = ?
        WHERE owner_type = ? AND owner_id = ?
        """,
        (to_owner_type, to_owner_id, from_owner_type, from_owner_id),
    )
    moved = cursor.rowcount
    connection.commit()
    connection.close()
    return max(0, moved)

def list_ready_document_ids() -> list:
    """Document IDs that are fully indexed and safe to retrieve from."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT document_id
        FROM documents
        WHERE status = 'ready'
        ORDER BY upload_time DESC
        """
    )
    rows = cursor.fetchall()
    connection.close()
    return [row[0] for row in rows if row and row[0]]


def list_active_index_document_ids() -> list:
    """IDs that may legitimately have Chroma rows (ready or in-flight)."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT document_id, status
        FROM documents
        """
    )
    rows = cursor.fetchall()
    connection.close()
    keep = {"ready", "uploaded", "extracting", "chunking", "embedding", "indexing"}
    return [row[0] for row in rows if row and row[0] and row[1] in keep]


def count_documents_with_filename(filename: str, *, exclude_document_id: str | None = None) -> int:
    if not filename:
        return 0
    connection = get_connection()
    cursor = connection.cursor()
    if exclude_document_id:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM documents
            WHERE filename = ? AND document_id != ?
            """,
            (filename, exclude_document_id),
        )
    else:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM documents
            WHERE filename = ?
            """,
            (filename,),
        )
    row = cursor.fetchone()
    connection.close()
    return int(row[0] or 0) if row else 0


def get_all_documents():

    connection = get_connection()

    cursor = connection.cursor()


    cursor.execute(
        """
        SELECT *
        FROM documents
        ORDER BY upload_time DESC
        """
    )


    documents = cursor.fetchall()

    connection.close()


    return [document_to_dict(doc) for doc in documents]

def get_document(document_id):

    connection = get_connection()

    cursor = connection.cursor()


    cursor.execute(
        """
        SELECT *
        FROM documents
        WHERE document_id = ?
        """,
        (document_id,)
    )


    document = cursor.fetchone()

    connection.close()


    return document_to_dict(document)

def delete_document(document_id):

    connection = get_connection()

    cursor = connection.cursor()

    for table in ("quote_region_cache", "chunk_evidence", "page_layouts"):
        try:
            cursor.execute(
                f"DELETE FROM {table} WHERE document_id = ?",
                (document_id,),
            )
        except sqlite3.OperationalError:
            pass

    cursor.execute(
        """
        DELETE FROM documents
        WHERE document_id = ?
        """,
        (document_id,)
    )


    deleted = cursor.rowcount


    connection.commit()

    connection.close()


    return deleted > 0

def update_document_status(
    document_id,
    status
):

    connection = get_connection()

    cursor = connection.cursor()


    cursor.execute(
        """
        UPDATE documents
        SET status = ?
        WHERE document_id = ?
        """,
        (
            status,
            document_id
        )
    )


    connection.commit()

    connection.close()


def update_document_index_error(
    document_id: str,
    message: str | None,
) -> None:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE documents
        SET index_error = ?
        WHERE document_id = ?
        """,
        (message, document_id),
    )

    connection.commit()
    connection.close()


def touch_document_index(document_id: str) -> None:
    """Heartbeat so the UI knows a long extract (OCR) is still alive."""
    if not document_id:
        return
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        UPDATE documents
        SET index_updated_at = ?
        WHERE document_id = ?
        """,
        (datetime.now().isoformat(), document_id),
    )
    connection.commit()
    connection.close()


def mark_document_index_failed(
    document_id: str,
    message: str,
) -> None:
    update_document_status(document_id, "failed")
    update_document_index_error(document_id, message)

