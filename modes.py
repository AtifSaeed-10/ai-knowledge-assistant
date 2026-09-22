"""
Product modes for DocuSage.

NORMAL         — existing RAG: question → retrieve (optional doc filter) → answer
SUPER_FOCUSED  — same RAG pipeline, retrieval scoped to one selected document
AGENTIC        — future: plan → multiple retrieval/tool steps → grounded answer
                 Not implemented. Do not pretend it is autonomous.

The RAG pipeline (ask_question / retrieve_candidates) stays the reusable
capability. Modes only change *scope* and *orchestration*, not scoring.
"""

from __future__ import annotations

from typing import Any

MODE_NORMAL = "normal"
MODE_SUPER_FOCUSED = "super_focused"
MODE_AGENTIC = "agentic"

VALID_MODES = frozenset(
    {
        MODE_NORMAL,
        MODE_SUPER_FOCUSED,
        MODE_AGENTIC,
    }
)

# Matches rag.py empty-retrieval copy. Do not invent a second unanswerable phrase.
INSUFFICIENT_CONTEXT_ANSWER = (
    "No relevant information found in the document."
)

_MODE_ALIASES = {
    "superfocused": MODE_SUPER_FOCUSED,
    "super_focused": MODE_SUPER_FOCUSED,
    "focused": MODE_SUPER_FOCUSED,
    "document": MODE_SUPER_FOCUSED,
}


def normalize_mode(mode: str | None) -> str:
    if not mode:
        return MODE_NORMAL
    value = mode.strip().lower().replace("-", "_").replace(" ", "_")
    value = _MODE_ALIASES.get(value, value)
    if value in VALID_MODES:
        return value
    return MODE_NORMAL


def resolve_document_scope(
    mode: str,
    document_ids: list[str] | None,
) -> list[str] | None:
    """
    Document IDs to pass into the existing retrieval stack.

    Super Focused: at most the first provided id (never other uploads).
    Returns None when Super Focused has no selected document — callers
    must short-circuit with the insufficient-context response and must
    not search the rest of the corpus.

    Normal / Agentic-disabled: pass through unchanged (None/[] = all docs).
    """
    normalized = normalize_mode(mode)
    if normalized != MODE_SUPER_FOCUSED:
        return document_ids

    ids = [doc_id for doc_id in (document_ids or []) if doc_id]
    if not ids:
        return None
    return [ids[0]]


def insufficient_context_payload() -> dict[str, Any]:
    return {
        "answer": INSUFFICIENT_CONTEXT_ANSWER,
        "sources": [],
        "prompt": None,
    }


def super_focused_has_scope(scoped_ids: list[str] | None) -> bool:
    return bool(scoped_ids)
