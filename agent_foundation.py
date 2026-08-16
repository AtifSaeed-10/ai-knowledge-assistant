"""
Agentic Mode — foundation only.

This module does not run an autonomous agent. It defines the seam so a later
phase can add planning / multi-step retrieval without rewriting RAG.

Mode split
----------
NORMAL
    question → retrieve_candidates → rerank → ask_question → answer

SUPER_FOCUSED
    same pipeline, document_ids scoped to one selected file (see modes.py)

AGENTIC (future)
    task → plan subtasks → call run_document_qa (and later other tools)
         → verify evidence → grounded final answer

The existing RAG stack is the reusable capability. Do not import LangChain
or LangGraph here. Do not pretend this module is autonomous.
"""

from __future__ import annotations

from typing import Any, Callable

from config import AGENTIC_MODE_ENABLED
from modes import MODE_AGENTIC, MODE_NORMAL, MODE_SUPER_FOCUSED, normalize_mode


# Tools an agent may call later. Names are stable; implementations wrap RAG.
TOOL_DOCUMENT_QA = "document_qa"


def is_agentic_enabled() -> bool:
    return bool(AGENTIC_MODE_ENABLED)


def effective_mode(requested: str | None) -> str:
    """Agentic requests fall back to normal until the flag is on."""
    mode = normalize_mode(requested)
    if mode == MODE_AGENTIC and not is_agentic_enabled():
        return MODE_NORMAL
    return mode


def run_document_qa(
    question: str,
    *,
    history=None,
    document_ids=None,
    generate: bool = True,
    ask_question: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Reusable single-shot RAG capability.

    An agent loop should call this per subtask instead of copying retrieval.
    """
    if ask_question is None:
        from rag import ask_question as _ask_question

        ask_question = _ask_question

    return ask_question(
        question,
        history,
        document_ids,
        generate=generate,
    )


def planned_agent_steps(task: str) -> list[dict[str, str]]:
    """
    Placeholder planner. Returns a single document_qa step.
    Not used in production until Agentic Mode is implemented.
    """
    return [
        {
            "tool": TOOL_DOCUMENT_QA,
            "task": task,
            "note": "Foundation placeholder — not executed as an agent loop.",
        }
    ]


__all__ = [
    "MODE_NORMAL",
    "MODE_SUPER_FOCUSED",
    "MODE_AGENTIC",
    "TOOL_DOCUMENT_QA",
    "effective_mode",
    "is_agentic_enabled",
    "planned_agent_steps",
    "run_document_qa",
]
