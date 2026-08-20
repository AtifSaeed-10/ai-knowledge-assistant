"""Resolve on-disk PDF paths for indexed documents."""

from __future__ import annotations

import os

from config import DATA_DIR
from database.document_store import get_document


def document_pdf_path(document_id: str) -> str | None:
    """Return the absolute PDF path for a document id, or None if unavailable."""
    row = get_document(document_id)
    if not row:
        return None
    filename = row.get("filename") or ""
    return pdf_path_for_filename(filename)


def pdf_path_for_filename(filename: str) -> str | None:
    if not filename:
        return None
    data_root = os.path.abspath(DATA_DIR)
    os.makedirs(data_root, exist_ok=True)
    candidate = os.path.abspath(os.path.join(data_root, filename))
    try:
        common = os.path.commonpath([data_root, candidate])
    except ValueError:
        return None
    if common != data_root:
        return None
    if not os.path.isfile(candidate):
        return None
    return candidate
