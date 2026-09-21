"""
When may we leave the document pipeline?

Empty retrieval still triggers web (Phase 1–2). If the files returned
passages but the final answer is a grounded refusal ("not in the document"),
Web-on also searches (Phase 3). Related pages can exist while the asked
fact does not. Triggers are about that gap, never about a topic or file.
"""

from __future__ import annotations

from typing import Any

from evidence_state import looks_like_evidence_refusal, normalize_evidence_text
from web_fallback.coverage import (
    passage_text_from_document,
    passages_are_off_topic,
    passages_miss_question,
)

ACTION_CONTINUE = "continue_generate"
ACTION_DOCUMENT = "return_document"
ACTION_WEB = "return_web"

REASON_DOC_SUFFICIENT = "doc_sufficient"
REASON_DOC_INSUFFICIENT_PRE_LLM = "doc_insufficient_pre_llm"
REASON_DOC_INSUFFICIENT_POST_LLM = "doc_insufficient_post_llm"
REASON_DOC_OFF_TOPIC = "doc_off_topic"
REASON_WEB_SKIPPED_TOGGLE_OFF = "web_skipped_toggle_off"
REASON_WEB_SKIPPED_DISABLED = "web_skipped_disabled"

# The model is talking about the user's files, not quoting a third-party "couldn't find".
_DOC_SCOPE_SNIPPETS = (
    "provided document",
    "provided documents",
    "provided context",
    "provided excerpts",
    "provided passages",
    "in the document",
    "in your document",
    "in the documents",
    "in your documents",
    "your documents",
    "the document only",
    "the documents only",
    "the document does not",
    "the documents do not",
    "the document did not",
    "the documents did not",
    "the text does not",
    "the passages do not",
    "retrieved passages",
    "not covered in the document",
    "not covered in the provided",
)

# Extra gap language beyond the shared evidence-refusal list.
_GAP_EXTRA = (
    "do not extend",
    "does not extend",
    "do not cover this",
    "does not cover this",
    "do not cover that",
    "does not cover that",
    "does not contain",
    "do not contain",
    "not covered in the document",
    "not covered in the provided",
    "not discussed in the document",
    "the document does not mention",
    "the documents do not mention",
    "the document does not discuss",
    "the documents do not discuss",
    "beyond the scope of the document",
    "beyond the provided document",
    "no details regarding",
    "provided passages discuss this",
    "supporting excerpt",
    "don't have that information",
    "do not have that information",
    "don't have this information",
    "no information in the provided",
    "i don't have that",
    "i do not have that",
)


def server_web_fallback_enabled() -> bool:
    from config import WEB_FALLBACK_ENABLED

    return bool(WEB_FALLBACK_ENABLED)


def is_pre_llm_insufficient(document_result: dict[str, Any] | None) -> bool:
    """
    True when retrieval produced nothing the model is allowed to answer from.

    A prompt means passages were selected. That is no longer the only gate:
    see decide_web_after_answer for post-generation refusals.
    """
    result = document_result or {}
    if result.get("prompt"):
        return False
    answer = str(result.get("answer") or "")
    return looks_like_evidence_refusal(answer)


def is_document_gap_answer(answer: str) -> bool:
    """
    True when a finished document answer says the asked fact is missing
    from the user's files. Works for any PDF; not topic-specific.
    """
    text = normalize_evidence_text(answer)
    if not text:
        return False
    has_gap = looks_like_evidence_refusal(text) or any(
        snippet in text for snippet in _GAP_EXTRA
    )
    if not has_gap:
        return False
    if any(snippet in text for snippet in _DOC_SCOPE_SNIPPETS):
        return True
    return "document" in text or "passages" in text or "context" in text or "files" in text


def _web_allowed(*, user_enabled: bool, server_enabled: bool | None) -> tuple[bool, str | None]:
    if server_enabled is None:
        server_enabled = server_web_fallback_enabled()
    if not server_enabled:
        return False, REASON_WEB_SKIPPED_DISABLED
    if not user_enabled:
        return False, REASON_WEB_SKIPPED_TOGGLE_OFF
    return True, None


def decide_web_fallback(
    *,
    user_enabled: bool,
    document_result: dict[str, Any] | None,
    server_enabled: bool | None = None,
    question: str = "",
) -> tuple[str, str]:
    """
    Pre-generation gate.

    continue_generate  — document prompt exists and looks on-topic
    return_document    — no prompt: small talk, or a miss with web not allowed
    return_web         — empty retrieval, or retrieved pages are off-topic,
                         and both flags are on
    """
    result = document_result or {}
    if result.get("prompt"):
        blob = passage_text_from_document(result)
        if question:
            off_topic = passages_are_off_topic(question, blob)
            missing = passages_miss_question(question, blob)
            if off_topic or missing:
                allowed, blocked = _web_allowed(
                    user_enabled=user_enabled,
                    server_enabled=server_enabled,
                )
                if allowed:
                    return (
                        ACTION_WEB,
                        REASON_DOC_OFF_TOPIC if off_topic else REASON_DOC_INSUFFICIENT_PRE_LLM,
                    )
        return ACTION_CONTINUE, REASON_DOC_SUFFICIENT

    if not is_pre_llm_insufficient(result):
        return ACTION_DOCUMENT, REASON_DOC_SUFFICIENT

    allowed, blocked = _web_allowed(
        user_enabled=user_enabled,
        server_enabled=server_enabled,
    )
    if not allowed:
        return ACTION_DOCUMENT, blocked or REASON_WEB_SKIPPED_TOGGLE_OFF
    return ACTION_WEB, REASON_DOC_INSUFFICIENT_PRE_LLM


def decide_web_after_answer(
    *,
    user_enabled: bool,
    answer: str,
    server_enabled: bool | None = None,
    question: str = "",
    passages: str | None = None,
) -> tuple[bool, str]:
    """
    After a document answer exists: search when that answer is a grounded
    miss, or when the retrieved pages do not cover the asked fact.
    """
    gap = is_document_gap_answer(answer)
    off_topic = bool(question) and passages is not None and passages_miss_question(
        question, passages
    )
    if not gap and not off_topic:
        return False, REASON_DOC_SUFFICIENT
    allowed, blocked = _web_allowed(
        user_enabled=user_enabled,
        server_enabled=server_enabled,
    )
    if not allowed:
        return False, blocked or REASON_WEB_SKIPPED_TOGGLE_OFF
    if gap:
        return True, REASON_DOC_INSUFFICIENT_POST_LLM
    return True, REASON_DOC_OFF_TOPIC
