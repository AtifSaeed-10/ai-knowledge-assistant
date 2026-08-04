import sqlite3

from config import SQLITE_DB_PATH


def get_connection():

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


    connection.commit()

    connection.close()