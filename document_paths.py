"""Resolve on-disk PDF paths for indexed documents."""

from __future__ import annotations

import os

from config import DATA_DIR
from database.document_store import get_document


def _safe_data_path(name: str) -> str | None:
    if not name:
        return None
    data_root = os.path.abspath(DATA_DIR)
    os.makedirs(data_root, exist_ok=True)
    candidate = os.path.abspath(os.path.join(data_root, name))
    try:
        common = os.path.commonpath([data_root, candidate])
    except ValueError:
        return None
    if common != data_root:
        return None
    return candidate


def stored_pdf_path(document_id: str, *, must_exist: bool = False) -> str | None:
    """Canonical on-disk path: DATA_DIR/{document_id}.pdf."""
    if not document_id or "/" in document_id or "\\" in document_id or ".." in document_id:
        return None
    candidate = _safe_data_path(f"{document_id}.pdf")
    if candidate is None:
        return None
    if must_exist and not os.path.isfile(candidate):
        return None
    return candidate


def document_pdf_path(document_id: str) -> str | None:
    """Return the absolute PDF path for a document id, or None if unavailable."""
    id_path = stored_pdf_path(document_id, must_exist=True)
    if id_path:
        return id_path
    row = get_document(document_id)
    if not row:
        return None
    filename = row.get("filename") or ""
    return pdf_path_for_filename(filename)


def pdf_path_for_filename(filename: str) -> str | None:
    candidate = _safe_data_path(filename)
    if candidate is None or not os.path.isfile(candidate):
        return None
    return candidate
