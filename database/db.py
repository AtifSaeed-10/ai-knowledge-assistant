import os
import sqlite3

from config import SQLITE_DB_PATH


def get_connection():

    parent = os.path.dirname(os.path.abspath(SQLITE_DB_PATH))
    if parent:
        os.makedirs(parent, exist_ok=True)

    connection = sqlite3.connect(
        SQLITE_DB_PATH
    )

    return connection



def init_db():

    connection = get_connection()

    cursor = connection.cursor()


    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (

            document_id TEXT PRIMARY KEY,

            filename TEXT NOT NULL,

            upload_time TEXT NOT NULL,

            total_pages INTEGER,

            total_chunks INTEGER,

            status TEXT DEFAULT 'uploaded'

        )
        """
    )


    # Migration:
    # Add status column if old database already exists
    try:
        cursor.execute(
            """
            ALTER TABLE documents
            ADD COLUMN status TEXT DEFAULT 'uploaded'
            """
        )

    except sqlite3.OperationalError:
        pass


    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            conversation_id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT 'New conversation',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            citations TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_messages_conversation
        ON messages (conversation_id, id)
        """
    )


    try:
        cursor.execute(
            """
            ALTER TABLE documents
            ADD COLUMN index_error TEXT
            """
        )

    except sqlite3.OperationalError:
        pass


    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS page_layouts (
            document_id TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            width REAL NOT NULL,
            height REAL NOT NULL,
            source TEXT NOT NULL,
            engine TEXT NOT NULL,
            span_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (document_id, page_number)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chunk_evidence (
            chunk_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            page_start INTEGER NOT NULL,
            page_end INTEGER NOT NULL,
            snippet TEXT,
            highlight_available INTEGER NOT NULL DEFAULT 0,
            match_type TEXT NOT NULL,
            source TEXT,
            text_engine TEXT,
            layout_engine TEXT,
            join_recovered INTEGER NOT NULL DEFAULT 0,
            ranges_json TEXT,
            regions_json TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chunk_evidence_document
        ON chunk_evidence (document_id)
        """
    )


    connection.commit()

    connection.close()