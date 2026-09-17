"""Validate assistant answers before persistence."""

from __future__ import annotations

import re

from answer_prompt import (
    INSUFFICIENT_CONTEXT_PHRASE,
    MISSING_IN_DOCUMENT_PHRASE,
    MISSING_EXAMPLE_PHRASE,
)

# Grounded "not found" responses are valid and should be saved.
_ALLOWED_GROUNDED_PHRASES = (
    INSUFFICIENT_CONTEXT_PHRASE.lower(),
    MISSING_IN_DOCUMENT_PHRASE.lower(),
    MISSING_EXAMPLE_PHRASE.lower(),
    "no relevant information found in the document.",
)

_BAD_PATTERNS = (
    "you didn't provide",
    "please provide more details",
)


def is_valid_response(answer: str) -> bool:
    if not answer or not str(answer).strip():
        return False

    normalized = re.sub(r"\s+", " ", str(answer).strip().lower())
    for phrase in _ALLOWED_GROUNDED_PHRASES:
        if phrase in normalized:
            return True

    for pattern in _BAD_PATTERNS:
        if pattern in normalized:
            return False

    # Generic refusals without grounded phrasing are not persisted.
    generic_refusals = (
        "i don't know",
        "i cannot answer",
    )
    for pattern in generic_refusals:
        if pattern in normalized and not any(
            allowed in normalized for allowed in _ALLOWED_GROUNDED_PHRASES
        ):
            return False

    return True
