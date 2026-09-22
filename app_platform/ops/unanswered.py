"""Classify grounded refusals for the operator dashboard."""

from __future__ import annotations

from grounding_verifier import is_blanket_refusal

CATEGORY_NOT_IN_DOCUMENT = "not_in_document"
CATEGORY_NO_CONTEXT = "not_enough_context"
CATEGORY_NO_PASSAGE = "no_relevant_passage"
CATEGORY_MISSING_EXAMPLE = "missing_example"
CATEGORY_EMPTY = "empty_answer"

_LABELS = {
    CATEGORY_NOT_IN_DOCUMENT: "Not in the document",
    CATEGORY_NO_CONTEXT: "Not enough context",
    CATEGORY_NO_PASSAGE: "No relevant passage",
    CATEGORY_MISSING_EXAMPLE: "No example in the document",
    CATEGORY_EMPTY: "Empty answer",
}


def unanswered_label(category: str | None) -> str:
    if not category:
        return "Couldn't answer"
    return _LABELS.get(category, category.replace("_", " ").capitalize())


def unanswered_category(answer: str) -> str | None:
    text = (answer or "").strip()
    if not text:
        return CATEGORY_EMPTY
    if not is_blanket_refusal(text):
        return None
    lowered = text.lower()
    if "example" in lowered:
        return CATEGORY_MISSING_EXAMPLE
    if "no relevant information" in lowered:
        return CATEGORY_NO_PASSAGE
    if "enough information" in lowered:
        return CATEGORY_NO_CONTEXT
    return CATEGORY_NOT_IN_DOCUMENT
