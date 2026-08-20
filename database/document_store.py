import sqlite3
import uuid
from datetime import datetime

from database.db import get_connection


def create_document(filename):

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
            total_chunks
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            document_id,
            filename,
            upload_time,
            0,
            0
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
    }

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

    for table in ("chunk_evidence", "page_layouts"):
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


def mark_document_index_failed(
    document_id: str,
    message: str,
) -> None:
    update_document_status(document_id, "failed")
    update_document_index_error(document_id, message)

