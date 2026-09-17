"""
Conversational query understanding for DocuSage.

Deterministic analysis decides whether a turn is a new question, a
continuation, or a presentation transform. The LLM rewriter is invoked
only when references still need resolving and a standalone query cannot
be composed from conversation structure.

This is not a phrase whitelist. Signals are linguistic:
anaphora, ordinals, length, content-word overlap, and request type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from config import MEMORY_WINDOW


INTENT_FACTUAL = "factual"
INTENT_DEFINITION = "definition"
INTENT_EXPLANATION = "explanation"
INTENT_SIMPLIFICATION = "simplification"
INTENT_ELABORATION = "elaboration"
INTENT_SUMMARY = "summary"
INTENT_KEY_POINTS = "key_points"
INTENT_COMPARISON = "comparison"
INTENT_EXAMPLE = "example"
INTENT_LISTING = "listing"
INTENT_WHY = "why"
INTENT_HOW = "how"
INTENT_CLARIFICATION = "clarification"
INTENT_MIXED = "mixed"

RELATION_NEW = "new"
RELATION_CONTINUE = "continue"
RELATION_TRANSFORM = "transform"

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = frozenset(
    """
    a an the and or but if then so of to for from in on at by with as
    is are was were be been being do does did doing can could should would
    will just about into over after before than too very also not no
    please me my we our you your what which who whom whose when where
    why how this that these those it its they them their
    any some there really still even much many
    """.split()
)

_ANAPHORA_RE = re.compile(
    r"\b(it|its|itself|this|that|these|those|they|them|their|theirs)\b",
    re.IGNORECASE,
)
_ORDINAL_RE = re.compile(
    r"\b(first|second|third|fourth|fifth|last|former|latter|previous|"
    r"above|other one|ones?)\b",
    re.IGNORECASE,
)
_BARE_FOLLOWUP_RE = re.compile(
    r"^\s*((why|how|and)\??|what about|and then)\b",
    re.IGNORECASE,
)

# Request-type families (stems / constructions, not canned utterances).
_INTENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (INTENT_EXAMPLE, re.compile(r"\b(examples?|illustrat(?:e|ion)|for instance)\b", re.I)),
    (INTENT_COMPARISON, re.compile(
        r"\b(compar(?:e|ison|ing)|versus|\bvs\.?\b|differences?)\b",
        re.I,
    )),
    (INTENT_WHY, re.compile(
        r"\b(why|what causes?|what is the (?:cause|purpose|reason)|what happens (?:if|when))\b",
        re.I,
    )),
    (INTENT_HOW, re.compile(
        r"\b(how (?:do|does|did|can|to|is|are)|step[ -]?by[ -]?step|"
        r"series of events|what events?|who throw[s]?|who threw|"
        r"what happens(?! (?:if|when)))\b",
        re.I,
    )),
    (INTENT_LISTING, re.compile(
        r"\b(types?|kinds?|categor(?:y|ies)|classif(?:y|ication)|enumerate|"
        r"list(?:ing)?|forms?|approaches)\b",
        re.I,
    )),
    (INTENT_SUMMARY, re.compile(
        r"\b(summar(?:y|ize|ise)|tldr|in brief|in short|shorter|briefly|"
        r"more concise|concisely)\b",
        re.I,
    )),
    (INTENT_KEY_POINTS, re.compile(r"\b(key points?|main points?|takeaways?|bullets?)\b", re.I)),
    (INTENT_SIMPLIFICATION, re.compile(
        r"\b(simpl(?:e|y|er|ify)|beginner|easier|plain(?:er)?|eli5)\b",
        re.I,
    )),
    (INTENT_ELABORATION, re.compile(
        r"\b(more detail|in detail|(?:in|more) depth|"
        r"explain(?:\s+\S+){0,3}\s+more|go deeper|"
        r"elaborat(?:e|ion)|expand)\b",
        re.I,
    )),
    (INTENT_CLARIFICATION, re.compile(
        r"\b((?:what does (?:that|this|it) mean)|clarif(?:y|ication)|"
        r"meaning of|what do you mean)\b",
        re.I,
    )),
    (INTENT_DEFINITION, re.compile(
        r"^\s*(what is|what are|what's|whats|define|definition of)\b",
        re.I,
    )),
]

_GENERIC_REQUEST_TOKENS = frozenset(
    {
        "give",
        "example",
        "examples",
        "explain",
        "explanation",
        "more",
        "detail",
        "details",
        "simple",
        "simply",
        "simpler",
        "simplify",
        "summary",
        "summarize",
        "summarise",
        "key",
        "points",
        "point",
        "short",
        "shorter",
        "deeper",
        "elaborate",
        "expand",
        "another",
        "easier",
        "beginner",
        "brief",
        "briefly",
        "list",
        "illustration",
        "illustrate",
        "compare",
        "comparison",
        "versus",
        "difference",
        "differences",
        "types",
        "type",
        "kinds",
        "kind",
        "make",
        "clarify",
        "clarification",
        "meaning",
        "forms",
        "form",
        "approaches",
        "approach",
        "categories",
        "category",
        "concise",
        "concisely",
    }
)

_DOCUMENT_META_TOKENS = frozenset(
    {
        "document",
        "documents",
        "passage",
        "passages",
        "context",
        "provided",
        "mention",
        "mentioned",
        "mentions",
        "say",
        "says",
        "according",
        "source",
        "sources",
        "text",
        "page",
        "pages",
        "corpus",
    }
)

_ASPECT_TOKENS = frozenset(
    {
        "limitation",
        "limitations",
        "advantage",
        "advantages",
        "disadvantage",
        "disadvantages",
        "benefit",
        "benefits",
        "drawback",
        "drawbacks",
        "application",
        "applications",
        "use",
        "uses",
        "useful",
        "usefulness",
        "purpose",
        "reason",
        "reasons",
        "cause",
        "causes",
        "example",
        "examples",
        "type",
        "types",
        "kind",
        "kinds",
        "category",
        "categories",
        "form",
        "forms",
        "approach",
        "approaches",
        "difference",
        "differences",
        "comparison",
        "meaning",
        "overview",
        "summary",
        "point",
        "points",
        "instance",
        "illustration",
    }
)

_TRANSFORM_INTENTS = frozenset(
    {
        INTENT_SIMPLIFICATION,
        INTENT_ELABORATION,
        INTENT_SUMMARY,
        INTENT_KEY_POINTS,
        INTENT_EXAMPLE,
        INTENT_CLARIFICATION,
    }
)

_DEPENDENT_INTENTS = _TRANSFORM_INTENTS | {
    INTENT_LISTING,
    INTENT_WHY,
    INTENT_HOW,
    INTENT_COMPARISON,
}

_ASSISTANT_HISTORY_CHARS = 600
_OVERLAP_NEW_TOPIC = 0.18
_SHORT_TURN_WORDS = 8
_ASPECT_FOLLOWUP_WORDS = 16

_LEADIN_RE = re.compile(
    r"^\s*(?:"
    r"what (?:is|are|was|were)|what's|whats|"
    r"who (?:is|are)|define|definition of|"
    r"explain|describe|tell me about"
    r")\b[:\s]*",
    re.I,
)
_TYPES_OF_RE = re.compile(
    r"\b(?:types?|kinds?|categor(?:y|ies)|forms?|examples?)\s+of\s+(.+?)\s*$",
    re.I,
)
_LIST_LEAD_RE = re.compile(
    r"\b(?:are|include[s]?|including|namely)\s+([^.?!]+)",
    re.I,
)
_BULLET_ITEM_RE = re.compile(
    r"(?m)^\s*(?:\d+[\.\)]\s+|[-*]\s+)(.+)$",
)
_ANAPHORA_REPLACE_RE = re.compile(
    r"\b(it|its|itself|this|that|these|those|they|them|their|theirs)\b",
    re.I,
)

_ORDINAL_INDEX = {
    "first": 0,
    "second": 1,
    "third": 2,
    "fourth": 3,
    "fifth": 4,
    "last": -1,
    "former": 0,
    "latter": -1,
    "previous": -1,
    "above": -1,
}


@dataclass
class TurnAnalysis:
    intent: str
    relation: str
    needs_rewrite: bool
    reason: str
    content_tokens: set[str] = field(default_factory=set)
    subject: str | None = None


def tokenize_content(text: str) -> set[str]:
    tokens = _TOKEN_RE.findall((text or "").lower())
    return {tok for tok in tokens if tok not in _STOPWORDS and len(tok) > 1}


def distinctive_topic_tokens(question: str) -> set[str]:
    """Content nouns that name a topic, not a request style or document meta."""
    content = tokenize_content(question)
    return content - _GENERIC_REQUEST_TOKENS - _DOCUMENT_META_TOKENS - _ASPECT_TOKENS


_SEARCH_ALL_PREFIX_RE = re.compile(
    r"^\s*(?:search\s+all(?:\s+(?:the\s+)?(?:documents?|pdfs?|files?))?"
    r"|across\s+(?:all\s+)?(?:the\s+)?(?:documents?|pdfs?|files?))"
    r"\s*[:\-–]?\s*",
    re.I,
)
_STRONG_TOPIC_SPLIT_RE = re.compile(
    r"\s*(?:[,;]?\s+)?(?:and\s+also|also(?:\s+please)?\s+tell\s+me(?:\s+about)?"
    r"|and\s+tell\s+me(?:\s+about)?|as\s+well\s+as)\s+",
    re.I,
)
# "who was X and what is Y" — a new question starts after and/comma.
_QUESTION_JOIN_RE = re.compile(
    r"\s*(?:,|;|\band)\s+(?=(?:what|who|how|why|when|where|which)\b)",
    re.I,
)


def strip_search_all_prefix(question: str) -> str:
    return _SEARCH_ALL_PREFIX_RE.sub("", question or "").strip()


def split_conjunctive_topics(question: str) -> list[str]:
    """
    Split “Hitler’s early life and also supervised learning” into topics.

    Bare “and” only splits when both sides name their own topic
    (two+ distinctive tokens). “father and son” stays one clause.
    “who was X and what is Y” also splits — each half is its own question.
    """
    text = strip_search_all_prefix(question)
    if not text:
        return []

    parts = [
        part.strip(" ?.!")
        for part in _STRONG_TOPIC_SPLIT_RE.split(text)
        if part.strip(" ?.!")
    ]
    if len(parts) >= 2:
        return parts[:4]

    question_parts = [
        part.strip(" ?.!")
        for part in _QUESTION_JOIN_RE.split(text)
        if part.strip(" ?.!")
    ]
    if len(question_parts) >= 2 and all(
        distinctive_topic_tokens(part) for part in question_parts[:4]
    ):
        return question_parts[:4]

    weak = re.split(r"\s+and\s+", text, maxsplit=1, flags=re.I)
    if len(weak) == 2:
        left, right = weak[0].strip(" ?.!"), weak[1].strip(" ?.!")
        if (
            len(distinctive_topic_tokens(left)) >= 2
            and len(distinctive_topic_tokens(right)) >= 2
        ):
            return [left, right]
    return [text]


def detect_intent(question: str) -> str:
    text = question or ""
    hits: list[str] = []
    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(text) and intent not in hits:
            hits.append(intent)

    if INTENT_DEFINITION in hits:
        others = [intent for intent in hits if intent != INTENT_DEFINITION]
        if len(others) == 1:
            return others[0]
        if len(others) >= 2:
            hits = others
        else:
            return INTENT_DEFINITION

    if INTENT_SIMPLIFICATION in hits and INTENT_ELABORATION in hits:
        hits = [intent for intent in hits if intent != INTENT_ELABORATION]
    if INTENT_SUMMARY in hits and INTENT_ELABORATION in hits:
        hits = [intent for intent in hits if intent != INTENT_ELABORATION]

    if len(hits) >= 2:
        return INTENT_MIXED
    if len(split_conjunctive_topics(text)) >= 2:
        return INTENT_MIXED
    if hits:
        return hits[0]
    stripped = text.strip()
    if stripped.endswith("?") or stripped.lower().startswith(("what", "who", "when", "where")):
        return INTENT_FACTUAL
    if re.match(r"^\s*explain\b", stripped, re.I):
        return INTENT_EXPLANATION
    return INTENT_FACTUAL


def _history_text(history: list[dict] | None) -> str:
    if not history:
        return ""
    parts: list[str] = []
    for message in history[-MEMORY_WINDOW:]:
        parts.append(str(message.get("content") or ""))
    return "\n".join(parts)


def _word_count(text: str) -> int:
    return len((text or "").split())


def last_user_text(history: list[dict] | None) -> str:
    if not history:
        return ""
    for message in reversed(history):
        if str(message.get("role") or "").lower() == "user":
            return str(message.get("content") or "").strip()
    return ""


def last_assistant_text(history: list[dict] | None) -> str:
    if not history:
        return ""
    for message in reversed(history):
        if str(message.get("role") or "").lower() == "assistant":
            return str(message.get("content") or "").strip()
    return ""


def has_unresolved_reference(question: str) -> bool:
    text = question or ""
    if _ANAPHORA_RE.search(text):
        return True
    if _ORDINAL_RE.search(text):
        return True
    if _BARE_FOLLOWUP_RE.search(text):
        return True
    return False


def looks_standalone(question: str) -> bool:
    """True when the utterance names its own topic without depending on prior turns."""
    text = (question or "").strip()
    if not text:
        return False
    content = tokenize_content(text)
    topical = content - _GENERIC_REQUEST_TOKENS
    if _ORDINAL_RE.search(text):
        return False
    if has_unresolved_reference(text) and len(topical) < 2:
        return False
    if len(topical) >= 2:
        return True
    if len(topical) == 1 and _word_count(text) >= 4 and not has_unresolved_reference(text):
        return True
    return False


def strip_question_leadin(text: str) -> str:
    cleaned = _LEADIN_RE.sub("", (text or "").strip()).strip()
    cleaned = re.sub(r"[?!.]+$", "", cleaned).strip()
    cleaned = re.sub(r"^(?:the|a|an)\s+", "", cleaned, flags=re.I).strip()
    return cleaned


def extract_focus_subject(history: list[dict] | None) -> str | None:
    """Best current topic from recent standalone user questions, not assistant prose."""
    if not history:
        return None
    user_turns = [
        str(message.get("content") or "").strip()
        for message in history
        if str(message.get("role") or "").lower() == "user" and str(message.get("content") or "").strip()
    ]
    for text in reversed(user_turns):
        if looks_standalone(text):
            subject = infer_subject_phrase(text)
            if subject:
                return subject
    if user_turns:
        return infer_subject_phrase(user_turns[-1])
    return None


def infer_subject_phrase(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None
    match = _TYPES_OF_RE.search(re.sub(r"[?!.]+$", "", raw))
    if match:
        phrase = match.group(1).strip(" .")
        phrase = re.sub(r"^(?:the|a|an)\s+", "", phrase, flags=re.I).strip()
        if phrase and not has_unresolved_reference(phrase):
            return phrase
        return None
    if has_unresolved_reference(raw) and not looks_standalone(raw):
        return None
    stripped = strip_question_leadin(raw)
    if stripped and stripped.lower() not in {"it", "this", "that", "them", "those"}:
        return stripped[:120]
    return None


def extract_enumerated_items(text: str) -> list[str]:
    """Pull ordered items from the latest assistant answer for ordinal follow-ups."""
    if not text:
        return []
    items: list[str] = []
    for match in _BULLET_ITEM_RE.finditer(text):
        item = _normalize_list_item(match.group(1))
        if item:
            items.append(item)
    if items:
        return items[:8]
    lead = _LIST_LEAD_RE.search(text)
    if lead:
        return _split_enumerated_span(lead.group(1))
    return []


def _normalize_list_item(text: str) -> str:
    item = (text or "").strip().rstrip(".;:")
    item = re.sub(r"^(?:the|a|an)\s+", "", item, flags=re.I).strip()
    if not item or len(item) > 80 or len(item.split()) > 8:
        return ""
    return item


def _split_enumerated_span(span: str) -> list[str]:
    span = re.sub(r"\s+(?:and|or)\s+", ", ", span or "", flags=re.I)
    parts: list[str] = []
    for raw in span.split(","):
        item = _normalize_list_item(raw)
        if item:
            parts.append(item)
    return parts[:8]


def _ordinal_index(question: str, n_items: int) -> int | None:
    match = _ORDINAL_RE.search(question or "")
    if not match or n_items <= 0:
        return None
    key = match.group(1).lower()
    if key in {"one", "ones"}:
        return None
    if key == "other one":
        return 1 if n_items >= 2 else n_items - 1
    index = _ORDINAL_INDEX.get(key)
    if index is None:
        return None
    if index < 0:
        return n_items - 1
    if index >= n_items:
        return None
    return index


def substitute_anaphora(question: str, subject: str) -> str:
    if not subject:
        return question
    if not _ANAPHORA_REPLACE_RE.search(question or ""):
        return question
    return _ANAPHORA_REPLACE_RE.sub(subject, question, count=1)


def compose_followup_query(
    question: str,
    history: list[dict] | None,
    analysis: TurnAnalysis | None = None,
) -> str | None:
    """
    Build a standalone search question from conversation structure.

    Returns None when the turn is not a follow-up or the subject cannot
    be recovered deterministically (caller may use the LLM rewriter).
    """
    if not history:
        return None
    if analysis is not None and not analysis.needs_rewrite:
        return None

    subject = (analysis.subject if analysis and analysis.subject else None) or extract_focus_subject(history)
    assistant = last_assistant_text(history)
    items = extract_enumerated_items(assistant)
    intent = analysis.intent if analysis else detect_intent(question)

    ordinal_idx = _ordinal_index(question, len(items))
    if ordinal_idx is not None and items:
        item = items[ordinal_idx]
        if subject and subject.lower() not in item.lower():
            return f"Explain {item} in {subject}"
        return f"Explain {item}"

    if not subject:
        return None

    if intent == INTENT_EXAMPLE:
        if re.search(r"\banother\b", question or "", re.I):
            return f"another example of {subject}"
        return f"example of {subject}"
    if intent == INTENT_LISTING:
        return f"types of {subject}"
    if intent == INTENT_SIMPLIFICATION:
        return f"Explain {subject} simply"
    if intent == INTENT_SUMMARY:
        return f"Summarize {subject}"
    if intent == INTENT_KEY_POINTS:
        return f"key points of {subject}"
    if intent == INTENT_ELABORATION:
        return f"Explain {subject} in more detail"
    if intent == INTENT_CLARIFICATION:
        return f"What does {subject} mean"
    if intent == INTENT_COMPARISON:
        if len(items) >= 2:
            return f"Compare {items[0]} and {items[1]}"
        replaced = substitute_anaphora(question, subject)
        if replaced != question:
            return replaced
        return f"difference in {subject}"
    if intent in {INTENT_WHY, INTENT_HOW, INTENT_EXPLANATION, INTENT_DEFINITION, INTENT_FACTUAL, INTENT_MIXED}:
        replaced = substitute_anaphora(question, subject)
        if replaced != question:
            return replaced
        aspects = tokenize_content(question) & _ASPECT_TOKENS
        if aspects:
            aspect = sorted(aspects, key=len, reverse=True)[0]
            return f"{aspect} of {subject}"
        if has_unresolved_reference(question):
            return f"{strip_question_leadin(question) or question} {subject}".strip()
        if len(distinctive_topic_tokens(question)) < 2:
            return f"{strip_question_leadin(question) or question.rstrip('?')} of {subject}"
    return None


def analyze_turn(question: str, history: list[dict] | None) -> TurnAnalysis:
    intent = detect_intent(question)
    content = tokenize_content(question)
    subject = extract_focus_subject(history) if history else infer_subject_phrase(question)

    if not history:
        return TurnAnalysis(
            intent=intent,
            relation=RELATION_NEW,
            needs_rewrite=False,
            reason="no_history",
            content_tokens=content,
            subject=subject,
        )

    history_tokens = tokenize_content(_history_text(history))
    last_user = last_user_text(history)
    last_user_tokens = tokenize_content(last_user)
    overlap_last_user = (
        len(content & last_user_tokens) / len(content) if content else 0.0
    )
    unresolved = has_unresolved_reference(question)
    standalone = looks_standalone(question)
    short = _word_count(question) <= _SHORT_TURN_WORDS
    distinctive = distinctive_topic_tokens(question)
    transform = intent in _TRANSFORM_INTENTS and (unresolved or not standalone)

    named_new_topic = (
        standalone
        and not unresolved
        and len(distinctive) >= 2
        and len(distinctive - last_user_tokens) >= 2
        and overlap_last_user < _OVERLAP_NEW_TOPIC
    )
    if named_new_topic:
        return TurnAnalysis(
            intent=intent,
            relation=RELATION_NEW,
            needs_rewrite=False,
            reason="topic_switch",
            content_tokens=content,
            subject=infer_subject_phrase(question),
        )

    new_single_topic = (
        standalone
        and not unresolved
        and len(distinctive) == 1
        and next(iter(distinctive)) not in last_user_tokens
        and next(iter(distinctive)) not in history_tokens
    )
    if new_single_topic:
        return TurnAnalysis(
            intent=intent,
            relation=RELATION_NEW,
            needs_rewrite=False,
            reason="topic_switch",
            content_tokens=content,
            subject=infer_subject_phrase(question),
        )

    aspect_followup = (
        len(distinctive) < 2
        and _word_count(question) <= _ASPECT_FOLLOWUP_WORDS
        and (unresolved or intent in _DEPENDENT_INTENTS or bool(content & (_ASPECT_TOKENS | _DOCUMENT_META_TOKENS)))
    )
    if aspect_followup and not named_new_topic:
        relation = RELATION_TRANSFORM if intent in _TRANSFORM_INTENTS else RELATION_CONTINUE
        return TurnAnalysis(
            intent=intent,
            relation=relation,
            needs_rewrite=True,
            reason="aspect_followup" if not unresolved else (
                "presentation_transform" if relation == RELATION_TRANSFORM else "unresolved_reference"
            ),
            content_tokens=content,
            subject=subject,
        )

    if standalone and not unresolved:
        return TurnAnalysis(
            intent=intent,
            relation=RELATION_CONTINUE if overlap_last_user >= _OVERLAP_NEW_TOPIC else RELATION_NEW,
            needs_rewrite=False,
            reason="self_contained",
            content_tokens=content,
            subject=infer_subject_phrase(question) or subject,
        )

    if transform:
        return TurnAnalysis(
            intent=intent,
            relation=RELATION_TRANSFORM,
            needs_rewrite=True,
            reason="presentation_transform",
            content_tokens=content,
            subject=subject,
        )

    if unresolved or (short and not standalone):
        return TurnAnalysis(
            intent=intent,
            relation=RELATION_CONTINUE,
            needs_rewrite=True,
            reason="unresolved_reference",
            content_tokens=content,
            subject=subject,
        )

    return TurnAnalysis(
        intent=intent,
        relation=RELATION_CONTINUE,
        needs_rewrite=False,
        reason="default_continue",
        content_tokens=content,
        subject=subject,
    )


def format_history_for_rewrite(history: list[dict] | None) -> str:
    if not history:
        return "No previous conversation."
    lines: list[str] = []
    for message in history[-MEMORY_WINDOW:]:
        role = str(message.get("role") or "user").capitalize()
        content = str(message.get("content") or "").strip()
        if role.lower() == "assistant" and len(content) > _ASSISTANT_HISTORY_CHARS:
            content = content[:_ASSISTANT_HISTORY_CHARS].rstrip() + "..."
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def format_history_for_grounding(history: list[dict] | None) -> str:
    """Compact history labeled as reference-resolution only, not evidence."""
    return format_history_for_rewrite(history)
