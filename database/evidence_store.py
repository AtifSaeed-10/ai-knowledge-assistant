"""SQLite sidecar for chunk → PDF evidence provenance.

Coordinates live here, not in Chroma. Retrieval/embeddings are unchanged.
"""

from __future__ import annotations

import json
from typing import Any

from database.db import get_connection


def replace_document_evidence(document_id: str, evidence: dict[str, Any]) -> None:
    """Replace all layout and chunk evidence rows for one document."""
    connection = get_connection()
    cursor = connection.cursor()
    try:
        _delete_for_document(cursor, document_id)
        for page in evidence.get("pages") or []:
            cursor.execute(
                """
                INSERT INTO page_layouts (
                    document_id,
                    page_number,
                    width,
                    height,
                    source,
                    engine,
                    span_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id,
                    int(page["page_number"]),
                    float(page["width"]),
                    float(page["height"]),
                    str(page.get("source") or ""),
                    str(page.get("engine") or ""),
                    int(page.get("span_count") or 0),
                ),
            )
        for chunk in evidence.get("chunks") or []:
            cursor.execute(
                """
                INSERT INTO chunk_evidence (
                    chunk_id,
                    document_id,
                    page_start,
                    page_end,
                    snippet,
                    highlight_available,
                    match_type,
                    source,
                    text_engine,
                    layout_engine,
                    join_recovered,
                    ranges_json,
                    regions_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(chunk["chunk_id"]),
                    document_id,
                    int(chunk["page_start"]),
                    int(chunk["page_end"]),
                    str(chunk.get("snippet") or ""),
                    1 if chunk.get("highlight_available") else 0,
                    str(chunk.get("match_type") or "failed"),
                    str(chunk.get("source") or ""),
                    str(chunk.get("text_engine") or ""),
                    str(chunk.get("layout_engine") or ""),
                    1 if chunk.get("join_recovered") else 0,
                    json.dumps(chunk.get("ranges") or []),
                    json.dumps(chunk.get("regions") or []),
                ),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _delete_for_document(cursor, document_id: str) -> None:
    cursor.execute(
        "DELETE FROM chunk_evidence WHERE document_id = ?",
        (document_id,),
    )
    cursor.execute(
        "DELETE FROM page_layouts WHERE document_id = ?",
        (document_id,),
    )


def delete_for_document(document_id: str) -> None:
    connection = get_connection()
    cursor = connection.cursor()
    try:
        _delete_for_document(cursor, document_id)
        connection.commit()
    finally:
        connection.close()


def _row_to_chunk(row: tuple) -> dict[str, Any]:
    (
        chunk_id,
        document_id,
        page_start,
        page_end,
        snippet,
        highlight_available,
        match_type,
        source,
        text_engine,
        layout_engine,
        join_recovered,
        ranges_json,
        regions_json,
    ) = row
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "page_start": page_start,
        "page_end": page_end,
        "snippet": snippet or "",
        "highlight_available": bool(highlight_available),
        "match_type": match_type,
        "source": source,
        "text_engine": text_engine,
        "layout_engine": layout_engine,
        "join_recovered": bool(join_recovered),
        "ranges": json.loads(ranges_json or "[]"),
        "regions": json.loads(regions_json or "[]"),
    }


def get_chunk_evidence(chunk_id: str) -> dict[str, Any] | None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            chunk_id,
            document_id,
            page_start,
            page_end,
            snippet,
            highlight_available,
            match_type,
            source,
            text_engine,
            layout_engine,
            join_recovered,
            ranges_json,
            regions_json
        FROM chunk_evidence
        WHERE chunk_id = ?
        """,
        (chunk_id,),
    )
    row = cursor.fetchone()
    connection.close()
    if not row:
        return None
    return _row_to_chunk(row)


def list_chunk_evidence(document_id: str) -> list[dict[str, Any]]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            chunk_id,
            document_id,
            page_start,
            page_end,
            snippet,
            highlight_available,
            match_type,
            source,
            text_engine,
            layout_engine,
            join_recovered,
            ranges_json,
            regions_json
        FROM chunk_evidence
        WHERE document_id = ?
        ORDER BY page_start, chunk_id
        """,
        (document_id,),
    )
    rows = cursor.fetchall()
    connection.close()
    return [_row_to_chunk(row) for row in rows]


def list_page_layouts(document_id: str) -> list[dict[str, Any]]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            document_id,
            page_number,
            width,
            height,
            source,
            engine,
            span_count
        FROM page_layouts
        WHERE document_id = ?
        ORDER BY page_number
        """,
        (document_id,),
    )
    rows = cursor.fetchall()
    connection.close()
    return [
        {
            "document_id": row[0],
            "page_number": row[1],
            "width": row[2],
            "height": row[3],
            "source": row[4],
            "engine": row[5],
            "span_count": row[6],
        }
        for row in rows
    ]
