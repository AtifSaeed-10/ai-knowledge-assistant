import os
import sqlite3

from database.connection import get_connection as _open_connection

_MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations")


def get_connection():

    return _open_connection()



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

    try:
        cursor.execute(
            """
            ALTER TABLE chunk_evidence
            ADD COLUMN segments_json TEXT
            """
        )
    except sqlite3.OperationalError:
        pass

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS quote_region_cache (
            chunk_id TEXT NOT NULL,
            quote_hash TEXT NOT NULL,
            document_id TEXT NOT NULL,
            quote_text TEXT NOT NULL,
            match_type TEXT NOT NULL,
            quote_highlight_available INTEGER NOT NULL DEFAULT 0,
            regions_json TEXT,
            page_start INTEGER,
            page_end INTEGER,
            created_at TEXT NOT NULL,
            PRIMARY KEY (chunk_id, quote_hash)
        )
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_quote_cache_document
        ON quote_region_cache (document_id)
        """
    )


    _add_missing_columns(cursor)
    _run_sql_migrations(cursor)

    connection.commit()

    connection.close()


# (table, column, definition) — SQLite has no ADD COLUMN IF NOT EXISTS.
_OWNERSHIP_COLUMNS = (
    ("documents", "owner_type", "TEXT"),
    ("documents", "owner_id", "TEXT"),
    ("conversations", "owner_type", "TEXT"),
    ("conversations", "owner_id", "TEXT"),
)


def _add_missing_columns(cursor):
    """Attach ownership columns to pre-existing tables."""
    for table, column, definition in _OWNERSHIP_COLUMNS:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        except sqlite3.OperationalError:
            pass


def _run_sql_migrations(cursor):
    """Apply idempotent .sql files in name order."""
    if not os.path.isdir(_MIGRATIONS_DIR):
        return
    for name in sorted(os.listdir(_MIGRATIONS_DIR)):
        if not name.endswith(".sql"):
            continue
        path = os.path.join(_MIGRATIONS_DIR, name)
        with open(path, "r", encoding="utf-8") as handle:
            cursor.executescript(handle.read())