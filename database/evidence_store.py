"""SQLite sidecar for chunk → PDF evidence provenance.

Coordinates live here, not in Chroma. Retrieval/embeddings are unchanged.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from database.db import get_connection


def quote_hash(quote: str) -> str:
    """Stable hash for sanitized quote text."""
    normalized = (quote or "").strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]


def document_evidence_summary(document_id: str) -> dict[str, Any]:
    """Aggregate highlight availability for a document's indexed chunks."""
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN highlight_available = 1 THEN 1 ELSE 0 END) AS highlighted
        FROM chunk_evidence
        WHERE document_id = ?
        """,
        (document_id,),
    )
    row = cursor.fetchone()
    connection.close()
    total = int(row[0] or 0) if row else 0
    highlighted = int(row[1] or 0) if row else 0
    return {
        "document_id": document_id,
        "chunk_evidence_count": total,
        "highlighted_chunk_count": highlighted,
        "has_evidence_data": total > 0,
        "highlight_ratio": (highlighted / total) if total else 0.0,
    }


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
                    regions_json,
                    segments_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    json.dumps(chunk.get("segments") or []),
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
        "DELETE FROM quote_region_cache WHERE document_id = ?",
        (document_id,),
    )
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
        segments_json,
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
        "segments": json.loads(segments_json or "[]"),
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
            regions_json,
            segments_json
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
            regions_json,
            segments_json
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


def get_quote_region_cache(chunk_id: str, cleaned_quote: str) -> dict[str, Any] | None:
    """Return cached quote→region mapping if present."""
    key = quote_hash(cleaned_quote)
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        SELECT
            chunk_id,
            quote_hash,
            document_id,
            quote_text,
            match_type,
            quote_highlight_available,
            regions_json,
            page_start,
            page_end
        FROM quote_region_cache
        WHERE chunk_id = ? AND quote_hash = ?
        """,
        (chunk_id, key),
    )
    row = cursor.fetchone()
    connection.close()
    if not row:
        return None
    return {
        "chunk_id": row[0],
        "quote_hash": row[1],
        "document_id": row[2],
        "quote_text": row[3],
        "match_type": row[4],
        "quote_highlight_available": bool(row[5]),
        "regions": json.loads(row[6] or "[]"),
        "page_start": row[7],
        "page_end": row[8],
    }


def upsert_quote_region_cache(
    *,
    chunk_id: str,
    document_id: str,
    quote_text: str,
    match_type: str,
    quote_highlight_available: bool,
    regions: list[dict[str, Any]] | None,
    page_start: int | None = None,
    page_end: int | None = None,
) -> None:
    """Persist quote→region result for faster repeat lookups."""
    key = quote_hash(quote_text)
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        """
        INSERT INTO quote_region_cache (
            chunk_id,
            quote_hash,
            document_id,
            quote_text,
            match_type,
            quote_highlight_available,
            regions_json,
            page_start,
            page_end,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(chunk_id, quote_hash) DO UPDATE SET
            document_id = excluded.document_id,
            quote_text = excluded.quote_text,
            match_type = excluded.match_type,
            quote_highlight_available = excluded.quote_highlight_available,
            regions_json = excluded.regions_json,
            page_start = excluded.page_start,
            page_end = excluded.page_end,
            created_at = excluded.created_at
        """,
        (
            chunk_id,
            key,
            document_id,
            quote_text,
            match_type,
            1 if quote_highlight_available else 0,
            json.dumps(regions or []),
            page_start,
            page_end,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    connection.commit()
    connection.close()


def delete_quote_region_cache_for_document(document_id: str) -> None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute(
        "DELETE FROM quote_region_cache WHERE document_id = ?",
        (document_id,),
    )
    connection.commit()
    connection.close()
