"""
RAG V2 Phase 1 — structure-aware, document-level chunking helpers.

Deterministic only (no LLM). Page boundaries are preserved as metadata;
chunks may span pages when needed for coherent context.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

# Parameters chosen for bge-small-en-v1.5 (~512 token limit):
# ~1200 chars stays comfortably under the embedding window while giving
# more context than the V1 page-isolated 800/100 setup.
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150
MIN_CHUNK_CHARS = 200
PAGE_JOIN = "\n\n"

SPLITTER_SEPARATORS = [
    "\n\n",
    "\n",
    ". ",
    "? ",
    "! ",
    "; ",
    ", ",
    " ",
    "",
]

# Deterministic heading patterns for academic / technical PDFs.
_HEADING_PATTERNS = [
    # Week 4 / Lecture 2 / Session 1: Topic
    re.compile(
        r"^(week|lecture|session|module|unit|chapter|lesson|day)\s*[-:]?\s*"
        r"(\d+|[ivxlcdm]+)\b.*$",
        re.IGNORECASE,
    ),
    # UNIT I / Unit II
    re.compile(r"^(UNIT\s+[IVXLCDM]+)\b.*$", re.IGNORECASE),
    # 1.2 Title / 2.5.1. Introduction / 1.1 What Is Machine Learning?
    re.compile(
        r"^(\d+(?:\.\d+){0,4}\.?)\s+[A-Z][A-Za-z0-9 ,:;\'\"()\-/&?]+\.?$"
    ),
    # Short ALL-CAPS title lines (conservative)
    re.compile(r"^[A-Z][A-Z0-9 ,:;\'\"()\-/&]{2,60}$"),
]


def slugify_section(title: str) -> str:
    """Stable section_id from a heading title."""
    if not title:
        return ""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:80]


def is_heading_line(line: str) -> bool:
    """Return True if a line looks like a reliable section heading."""
    text = line.strip()
    if not text or len(text) > 80:
        return False
    # Reject lines that look like body sentences.
    if text.endswith(".") and not re.match(r"^\d+(\.\d+)+\.?$", text.split()[0]):
        # Numbered headings rarely end with a period alone as full sentence;
        # allow "1.2. Title" style via patterns below.
        words = text.split()
        if len(words) > 12:
            return False
    word_count = len(text.split())
    if word_count > 14:
        return False

    for pattern in _HEADING_PATTERNS:
        if pattern.match(text):
            # Avoid matching single short tokens that are not titles.
            if pattern is _HEADING_PATTERNS[-1] and word_count < 2:
                return False
            return True
    return False


def build_document_text(
    pages: list[dict[str, Any]],
) -> tuple[str, list[tuple[int, int, int]]]:
    """
    Concatenate page texts and return (full_text, page_spans).

    Each page_span is (start_char, end_char, page_number) for the page
    text region inside full_text (exclusive end).
    """
    parts: list[str] = []
    page_spans: list[tuple[int, int, int]] = []
    cursor = 0

    usable = [
        p for p in pages
        if (p.get("text") or "").strip()
    ]
    for i, page in enumerate(usable):
        text = (page.get("text") or "").strip()
        if i > 0:
            cursor += len(PAGE_JOIN)
        start = cursor
        end = start + len(text)
        page_spans.append((start, end, int(page["page_number"])))
        parts.append(text)
        cursor = end

    return PAGE_JOIN.join(parts), page_spans


def build_section_ranges(
    full_text: str,
) -> list[tuple[int, int, str, str]]:
    """
    Scan lines for headings; return ranges
    (start, end, section_title, section_id) covering the document.
    """
    if not full_text:
        return []

    headings: list[tuple[int, str]] = []
    offset = 0
    for line in full_text.splitlines(keepends=True):
        raw = line.rstrip("\r\n")
        if is_heading_line(raw):
            headings.append((offset, raw.strip()))
        offset += len(line)

    if not headings:
        return [(0, len(full_text), "", "")]

    ranges: list[tuple[int, int, str, str]] = []
    # Preamble before first heading.
    if headings[0][0] > 0:
        ranges.append((0, headings[0][0], "", ""))

    for i, (start, title) in enumerate(headings):
        end = headings[i + 1][0] if i + 1 < len(headings) else len(full_text)
        section_id = slugify_section(title)
        ranges.append((start, end, title, section_id))

    return ranges


def pages_for_span(
    start: int,
    end: int,
    page_spans: list[tuple[int, int, int]],
) -> tuple[int, int]:
    """Map a character span to (page_start, page_end)."""
    if not page_spans:
        return (1, 1)

    # Clamp to document bounds.
    start = max(0, start)
    end = max(start, end)

    touched: list[int] = []
    for p_start, p_end, page_number in page_spans:
        # Overlap of [start, end) with [p_start, p_end)
        if start < p_end and end > p_start:
            touched.append(page_number)

    if not touched:
        # Fallback: nearest page by start offset.
        nearest = min(
            page_spans,
            key=lambda s: abs(s[0] - start),
        )
        return (nearest[2], nearest[2])

    return (touched[0], touched[-1])


def section_for_span(
    start: int,
    end: int,
    section_ranges: list[tuple[int, int, str, str]],
) -> tuple[str, str]:
    """Prefer the section covering the chunk start."""
    if not section_ranges:
        return ("", "")

    for s_start, s_end, title, section_id in section_ranges:
        if s_start <= start < s_end:
            return (title, section_id)

    # Overlap fallback.
    for s_start, s_end, title, section_id in section_ranges:
        if start < s_end and end > s_start:
            return (title, section_id)

    return ("", "")


def find_chunk_offsets(full_text: str, chunk_text: str, search_from: int) -> tuple[int, int]:
    """
    Locate chunk_text in full_text starting near search_from.
    RecursiveCharacterTextSplitter preserves substrings, so find works.
    """
    idx = full_text.find(chunk_text, search_from)
    if idx == -1:
        idx = full_text.find(chunk_text)
    if idx == -1:
        # Last resort: treat as starting at search_from.
        return (search_from, search_from + len(chunk_text))
    return (idx, idx + len(chunk_text))


def merge_tiny_chunks(
    chunks: list[dict[str, Any]],
    min_chars: int = MIN_CHUNK_CHARS,
) -> list[dict[str, Any]]:
    """
    Merge chunks shorter than min_chars into the previous chunk.
    Recomputes page_start/page_end and prefers the previous section.
    """
    if not chunks:
        return []

    merged: list[dict[str, Any]] = []
    for chunk in chunks:
        text = chunk["text"]
        if merged and len(text.strip()) < min_chars:
            prev = merged[-1]
            prev["text"] = prev["text"] + PAGE_JOIN + text
            prev["page_end"] = max(prev["page_end"], chunk["page_end"])
            prev["page_number"] = prev["page_start"]
            prev["char_count"] = len(prev["text"])
            # Keep previous section metadata (parent of the tiny tail).
        else:
            merged.append(dict(chunk))

    # If the first chunk alone is tiny and there is a next, fold forward.
    if len(merged) >= 2 and len(merged[0]["text"].strip()) < min_chars:
        first = merged.pop(0)
        nxt = merged[0]
        nxt["text"] = first["text"] + PAGE_JOIN + nxt["text"]
        nxt["page_start"] = min(first["page_start"], nxt["page_start"])
        nxt["page_end"] = max(first["page_end"], nxt["page_end"])
        nxt["page_number"] = nxt["page_start"]
        nxt["char_count"] = len(nxt["text"])
        if not nxt.get("section_title") and first.get("section_title"):
            nxt["section_title"] = first["section_title"]
            nxt["section_id"] = first["section_id"]
            nxt["parent_id"] = first["parent_id"]

    return merged


def create_text_splitter(
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=SPLITTER_SEPARATORS,
        length_function=len,
        is_separator_regex=False,
    )


def build_chunks_from_pages(
    pages: list[dict[str, Any]],
    document_id: str,
    *,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    min_chunk_chars: int = MIN_CHUNK_CHARS,
) -> list[dict[str, Any]]:
    """
    Document-level structure-aware chunking.

    Returns chunk dicts with text + metadata fields ready for Chroma.
    Neighbor IDs use `{document_id}_{chunk_index}`.
    """
    full_text, page_spans = build_document_text(pages)
    if not full_text.strip():
        return []

    section_ranges = build_section_ranges(full_text)
    splitter = create_text_splitter(chunk_size, chunk_overlap)
    pieces = splitter.split_text(full_text)

    raw_chunks: list[dict[str, Any]] = []
    search_from = 0
    for piece in pieces:
        start, end = find_chunk_offsets(full_text, piece, search_from)
        search_from = max(search_from, start + 1)

        page_start, page_end = pages_for_span(start, end, page_spans)
        section_title, section_id = section_for_span(
            start, end, section_ranges
        )

        raw_chunks.append(
            {
                "text": piece,
                "page_number": page_start,
                "page_start": page_start,
                "page_end": page_end,
                "section_title": section_title,
                "section_id": section_id,
                "parent_id": section_id,
                "char_count": len(piece),
            }
        )

    merged = merge_tiny_chunks(raw_chunks, min_chars=min_chunk_chars)

    # Assign indices and neighbor relationships.
    final: list[dict[str, Any]] = []
    n = len(merged)
    for i, chunk in enumerate(merged):
        chunk_id = f"{document_id}_{i}"
        prev_id = f"{document_id}_{i - 1}" if i > 0 else ""
        next_id = f"{document_id}_{i + 1}" if i < n - 1 else ""
        final.append(
            {
                "text": chunk["text"],
                "page_number": chunk["page_start"],
                "page_start": chunk["page_start"],
                "page_end": chunk["page_end"],
                "section_title": chunk.get("section_title") or "",
                "section_id": chunk.get("section_id") or "",
                "parent_id": chunk.get("parent_id") or "",
                "char_count": len(chunk["text"]),
                "chunk_index": i,
                "chunk_id": chunk_id,
                "prev_chunk_id": prev_id,
                "next_chunk_id": next_id,
            }
        )

    return final


def chroma_metadata_for_chunk(
    chunk: dict[str, Any],
    document_id: str,
    filename: str,
) -> dict[str, Any]:
    """Scalar-only metadata dict for Chroma storage."""
    return {
        "document_id": document_id,
        "filename": filename,
        "chunk_index": int(chunk["chunk_index"]),
        "page_number": int(chunk["page_number"]),
        "page_start": int(chunk["page_start"]),
        "page_end": int(chunk["page_end"]),
        "section_title": str(chunk.get("section_title") or ""),
        "section_id": str(chunk.get("section_id") or ""),
        "parent_id": str(chunk.get("parent_id") or ""),
        "char_count": int(chunk.get("char_count") or len(chunk["text"])),
        "prev_chunk_id": str(chunk.get("prev_chunk_id") or ""),
        "next_chunk_id": str(chunk.get("next_chunk_id") or ""),
    }
