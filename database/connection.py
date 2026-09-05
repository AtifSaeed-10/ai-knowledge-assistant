"""
Single place that decides where the relational database lives.

`DATABASE_URL` is the deployment-facing setting; the legacy `SQLITE_DB_PATH`
still works so existing local setups keep running. Postgres is rejected with
a clear message until a driver is added, rather than silently writing to a
local file.
"""

from __future__ import annotations

import os
import sqlite3

from app_platform.settings import DATABASE_URL
from config import SQLITE_DB_PATH

_SQLITE_PREFIXES = ("sqlite:///", "sqlite://")


def _sqlite_path_from_url(url: str) -> str:
    for prefix in _SQLITE_PREFIXES:
        if url.startswith(prefix):
            remainder = url[len(prefix) :]
            # sqlite:////abs/path keeps a leading slash after the prefix.
            return remainder or SQLITE_DB_PATH
    return url


def database_path() -> str:
    """Resolve the SQLite file path for this deployment."""
    # An explicit legacy override wins so existing .env files are unaffected.
    if os.getenv("SQLITE_DB_PATH") and not os.getenv("DATABASE_URL"):
        return SQLITE_DB_PATH

    url = (DATABASE_URL or "").strip()
    if not url:
        return SQLITE_DB_PATH
    if url.startswith("postgres://") or url.startswith("postgresql://"):
        raise RuntimeError(
            "DATABASE_URL points at Postgres but no Postgres driver is installed. "
            "Install one and extend database/connection.py before switching."
        )
    return _sqlite_path_from_url(url)


def get_connection() -> sqlite3.Connection:
    path = database_path()
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    return sqlite3.connect(path)
