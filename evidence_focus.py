"""
Lightweight evidence-role checks for grounded answering.

Does not rescore MiniLM. Labels passages so the answer prompt and
citation filter can distinguish support from related-but-wrong excerpts.
"""

from __future__ import annotations

import re

from conversation_query import (
    INTENT_EXAMPLE,
    INTENT_HOW,
    INTENT_LISTING,
    INTENT_WHY,
    TurnAnalysis,
    tokenize_content,
)

ROLE_SUPPORT = "support"
ROLE_RELATED = "related"
ROLE_MISMATCH = "mismatch"
ROLE_UNKNOWN = "unknown"

_GENERIC_QUERY_TOKENS = frozenset(
    {
        "type",
        "types",
        "kind",
        "kinds",
        "category",
        "categories",
        "form",
        "forms",
        "example",
        "examples",
        "explain",
        "list",
        "compare",
        "difference",
        "why",
        "how",
        "what",
        "give",
        "another",
        "simply",
        "simple",
        "summarize",
        "summary",
        "key",
        "points",
        "approach",
        "approaches",
    }
)

_TYPES_OF_RE = re.compile(
    r"\b(?:types?|kinds?|categor(?:y|ies)|forms?|classes|approaches)\s+of\s+(.{3,80}?)(?:[:;.]|,|\bis\b|\bare\b|$)",
    re.I,
)
_CLASSIFIED_INTO_RE = re.compile(
    r"(.{3,100}?)\s+(?:can be |may be |is |are )?(?:classified|divided|grouped|split|organized)\s+(?:into|as)\s+(.{5,160})",
    re.I,
)
_IS_TYPE_OF_RE = re.compile(
    r"\b(is|are)\s+(?:a |an |one )?(?:type|kind|category|form|class|branch)\s+of\b",
    re.I,
)
_EXAMPLE_CUE_RE = re.compile(
    r"\b(for example|example|for instance|such as|e\.g\.|illustration|consider(?: this)?|imagine)\b",
    re.I,
)
_REASON_CUE_RE = re.compile(
    r"\b(because|therefore|so that|reason|useful|allows|enables|in order|"
    r"due to|leads to|improves|reduces|better when|purpose)\b",
    re.I,
)
_MECHANISM_CUE_RE = re.compile(
    r"\b(by|step|steps|process|algorithm|procedure|works by|computed|"
    r"calculate|using|mechanism)\b",
    re.I,
)


def subject_tokens_from_query(search_query: str) -> set[str]:
    tokens = tokenize_content(search_query or "")
    return {tok for tok in tokens if tok not in _GENERIC_QUERY_TOKENS and len(tok) > 2}


def _subject_mentioned(text: str, subject_tokens: set[str]) -> bool:
    if not subject_tokens:
        return False
    found = tokenize_content(text)
    if len(subject_tokens) <= 2:
        return subject_tokens <= found
    return (len(found & subject_tokens) / len(subject_tokens)) >= 0.6


def _cover(tokens: set[str], subject_tokens: set[str]) -> bool:
    if not subject_tokens:
        return False
    if len(subject_tokens) <= 2:
        return subject_tokens <= tokens
    return (len(tokens & subject_tokens) / len(subject_tokens)) >= 0.6


def passage_taxonomy_role(text: str, subject_tokens: set[str]) -> str:
    """
    support  — passage classifies THIS subject
    mismatch — subject appears as a member of a different/parent taxonomy
    related  — subject mentioned without an explicit type-list of it
    unknown  — subject not established in the passage
    """
    if not (text or "").strip() or not subject_tokens:
        return ROLE_UNKNOWN

    mentioned = _subject_mentioned(text, subject_tokens)

    for match in _TYPES_OF_RE.finditer(text):
        of_what = tokenize_content(match.group(1))
        if _cover(of_what, subject_tokens):
            return ROLE_SUPPORT

    for match in _CLASSIFIED_INTO_RE.finditer(text):
        entity = tokenize_content(match.group(1)[-80:])
        members = tokenize_content(match.group(2))
        entity_is_subject = _cover(entity, subject_tokens)
        if entity_is_subject:
            return ROLE_SUPPORT
        if _cover(members, subject_tokens) and not entity_is_subject:
            return ROLE_MISMATCH

    if mentioned and _IS_TYPE_OF_RE.search(text):
        # "supervised learning is a type of machine learning"
        return ROLE_MISMATCH

    if mentioned:
        return ROLE_RELATED
    return ROLE_UNKNOWN


def passage_example_role(text: str, subject_tokens: set[str]) -> str:
    if not (text or "").strip():
        return ROLE_UNKNOWN
    has_cue = bool(_EXAMPLE_CUE_RE.search(text))
    if has_cue:
        return ROLE_SUPPORT
    if subject_tokens and _subject_mentioned(text, subject_tokens):
        return ROLE_MISMATCH
    return ROLE_UNKNOWN


def passage_reason_role(text: str, subject_tokens: set[str], *, how: bool = False) -> str:
    if not (text or "").strip():
        return ROLE_UNKNOWN
    cue = _MECHANISM_CUE_RE if how else _REASON_CUE_RE
    has_cue = bool(cue.search(text))
    mentioned = _subject_mentioned(text, subject_tokens) if subject_tokens else has_cue
    if has_cue and mentioned:
        return ROLE_SUPPORT
    if mentioned:
        return ROLE_RELATED
    return ROLE_UNKNOWN


def passage_roles(
    chunks: list[str],
    search_query: str,
    analysis: TurnAnalysis | None,
) -> list[str]:
    subject_tokens = subject_tokens_from_query(search_query)
    intent = analysis.intent if analysis else ""
    roles: list[str] = []
    for chunk in chunks:
        if intent == INTENT_LISTING:
            roles.append(passage_taxonomy_role(chunk, subject_tokens))
        elif intent == INTENT_EXAMPLE:
            roles.append(passage_example_role(chunk, subject_tokens))
        elif intent == INTENT_WHY:
            roles.append(passage_reason_role(chunk, subject_tokens, how=False))
        elif intent == INTENT_HOW:
            roles.append(passage_reason_role(chunk, subject_tokens, how=True))
        else:
            if subject_tokens and _subject_mentioned(chunk, subject_tokens):
                roles.append(ROLE_SUPPORT)
            elif subject_tokens:
                roles.append(ROLE_RELATED)
            else:
                roles.append(ROLE_UNKNOWN)
    return roles


def citation_allowlist(
    chunks: list[str],
    search_query: str,
    analysis: TurnAnalysis | None,
) -> set[int] | None:
    """
    Extra citation filter on top of CITATION_MIN_RELEVANCE.

    None: leave threshold-only behavior unchanged.
    Empty set: do not cite (related-but-wrong / missing example).
    """
    if not analysis or not chunks:
        return None
    intent = analysis.intent
    if intent not in {INTENT_LISTING, INTENT_EXAMPLE}:
        if intent in {INTENT_WHY, INTENT_HOW}:
            roles = passage_roles(chunks, search_query, analysis)
            support = {i for i, role in enumerate(roles) if role == ROLE_SUPPORT}
            return support or None
        return None

    roles = passage_roles(chunks, search_query, analysis)
    support = {i for i, role in enumerate(roles) if role == ROLE_SUPPORT}
    if support:
        return support
    return set()


def format_evidence_notes(
    chunks: list[str],
    metadata: list[dict] | None,
    search_query: str,
    analysis: TurnAnalysis | None,
) -> str:
    if not analysis or analysis.intent not in {
        INTENT_LISTING,
        INTENT_EXAMPLE,
        INTENT_WHY,
        INTENT_HOW,
    }:
        return ""

    roles = passage_roles(chunks, search_query, analysis)
    metas = metadata or []
    lines: list[str] = []
    for index, role in enumerate(roles):
        meta = metas[index] if index < len(metas) else {}
        filename = (meta or {}).get("filename") or "document"
        page = (meta or {}).get("page_number")
        if page is None:
            page = (meta or {}).get("page_start")
        try:
            page_bit = f" p.{int(page)}" if page is not None and int(page) >= 1 else ""
        except (TypeError, ValueError):
            page_bit = ""
        if analysis.intent == INTENT_LISTING and role == ROLE_MISMATCH:
            lines.append(
                f"- {filename}{page_bit}: classifies a broader or different concept; "
                "not a type-list of the requested subject."
            )
        elif analysis.intent == INTENT_LISTING and role == ROLE_SUPPORT:
            lines.append(
                f"- {filename}{page_bit}: appears to classify the requested subject."
            )
        elif analysis.intent == INTENT_EXAMPLE and role == ROLE_SUPPORT:
            lines.append(f"- {filename}{page_bit}: contains example language.")
        elif analysis.intent == INTENT_EXAMPLE and role != ROLE_SUPPORT:
            lines.append(f"- {filename}{page_bit}: no clear example of the requested subject.")
        elif analysis.intent in {INTENT_WHY, INTENT_HOW} and role != ROLE_SUPPORT:
            kind = "how" if analysis.intent == INTENT_HOW else "why"
            lines.append(
                f"- {filename}{page_bit}: may mention the topic without explaining {kind}."
            )

    if analysis.intent == INTENT_LISTING and ROLE_SUPPORT not in roles:
        lines.append(
            "No passage appears to classify this subject. "
            "Do not treat a parent taxonomy as the answer."
        )
    if analysis.intent == INTENT_EXAMPLE and ROLE_SUPPORT not in roles:
        lines.append(
            "No passage appears to contain an example of this subject."
        )
    if not lines:
        return ""
    return "Evidence notes (internal; never mention these labels to the user):\n" + "\n".join(lines)
