"""
Web fallback — document-first, optional trusted-site lookup.

This is not an agent. The PDF RAG pipeline stays unchanged. When a question
cannot be answered from retrieved passages, and the user has turned the
toggle on, this package runs a second pass against a search provider.

Phase 3 also searches after a grounded document answer that says the asked
fact is not in the files, and keeps the PDF prose for what the files did cover.
"""

from web_fallback.decision import (
    ACTION_CONTINUE,
    ACTION_DOCUMENT,
    ACTION_WEB,
    REASON_DOC_INSUFFICIENT_POST_LLM,
    REASON_DOC_INSUFFICIENT_PRE_LLM,
    REASON_DOC_OFF_TOPIC,
    REASON_DOC_SUFFICIENT,
    REASON_WEB_SKIPPED_DISABLED,
    REASON_WEB_SKIPPED_TOGGLE_OFF,
    is_document_gap_answer,
    is_pre_llm_insufficient,
)
from web_fallback.orchestrator import (
    resolve_after_document_answer,
    resolve_after_document_pass,
)
from web_fallback.types import ORIGIN_DOCUMENT, ORIGIN_MIXED, ORIGIN_WEB_FALLBACK

__all__ = [
    "ACTION_CONTINUE",
    "ACTION_DOCUMENT",
    "ACTION_WEB",
    "ORIGIN_DOCUMENT",
    "ORIGIN_MIXED",
    "ORIGIN_WEB_FALLBACK",
    "REASON_DOC_INSUFFICIENT_POST_LLM",
    "REASON_DOC_INSUFFICIENT_PRE_LLM",
    "REASON_DOC_OFF_TOPIC",
    "REASON_DOC_SUFFICIENT",
    "REASON_WEB_SKIPPED_DISABLED",
    "REASON_WEB_SKIPPED_TOGGLE_OFF",
    "is_document_gap_answer",
    "is_pre_llm_insufficient",
    "resolve_after_document_answer",
    "resolve_after_document_pass",
]
