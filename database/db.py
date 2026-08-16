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


    connection.commit()

    connection.close()