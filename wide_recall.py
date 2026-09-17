"""
Wider recall for plot, summary, and event questions.

Short definition questions stay on the normal pool. Story-arc and
"what happened" questions need more pages and extra lexical probes so a
rare event (an apple, a later chapter) is not drowned by the hero's name.
"""

from __future__ import annotations

import re

from conversation_query import (
    INTENT_COMPARISON,
    INTENT_HOW,
    INTENT_KEY_POINTS,
    INTENT_SUMMARY,
    INTENT_WHY,
    _STOPWORDS,
    distinctive_topic_tokens,
)

WIDE_RECALL_RE = re.compile(
    r"\b("
    r"summar(?:y|ize|ise)|overview|throughout|whole (?:book|story|novel|text)|"
    r"from (?:the )?(?:beginning|start|chapter)|until |to (?:his |her )?death|"
    r"changing (?:attitude|feelings?)|series of events|what happens|"
    r"how did|who throw[s]?|who threw|who killed|who kills|lodged|"
    r"from chapter|later in|towards? the end|walk me through"
    r")\b",
    re.I,
)

COMFORT_TOP_K = 8
WIDE_TOP_K = 14
WIDE_CANDIDATE_K = 36
WIDE_RERANK_K = 36
WIDE_EXTRAS = 10
WIDE_PER_QUERY_K = 4
NEIGHBOR_EXTRAS = 6


def is_wide_recall_question(question: str, intent: str | None = None) -> bool:
    text = question or ""
    distinctive = len(distinctive_topic_tokens(text))
    if intent in {INTENT_SUMMARY, INTENT_KEY_POINTS, INTENT_COMPARISON} and distinctive >= 3:
        return True
    if intent in {INTENT_HOW, INTENT_WHY} and distinctive >= 4:
        return True
    return bool(WIDE_RECALL_RE.search(text))


def skip_mechanism_role_gating(question: str, intent: str | None = None) -> bool:
    """
    Textbook how/why questions still need mechanism cues.
    Story-arc questions should not be refused because a scene has no 'because'.
    """
    return is_wide_recall_question(question, intent)


def lexical_probe_queries(question: str, *, limit: int = 6) -> list[str]:
    """
    Search the latter half of the question — usually the event, not the hero.

    "Gregor getting an apple lodged in his back" → apple / apple lodged / throws.
    """
    tokens = [
        tok
        for tok in re.findall(r"[a-z0-9]+", (question or "").lower())
        if tok not in _STOPWORDS and len(tok) >= 4
    ]
    if not tokens:
        return []
    focus = tokens if len(tokens) < 4 else tokens[len(tokens) // 2 :]
    probes: list[str] = []
    seen: set[str] = set()

    def _add(item: str) -> None:
        key = item.strip().lower()
        if not key or key in seen:
            return
        seen.add(key)
        probes.append(item)

    for index in range(len(focus) - 1):
        _add(f"{focus[index]} {focus[index + 1]}")
    for tok in focus:
        if len(tok) >= 5:
            _add(tok)
    return probes[:limit]


def recall_settings(*, wide: bool) -> dict[str, int]:
    if wide:
        return {
            "top_k": WIDE_TOP_K,
            "candidate_k": WIDE_CANDIDATE_K,
            "rerank_candidate_k": WIDE_RERANK_K,
            "extras_budget": WIDE_EXTRAS,
            "per_query_k": WIDE_PER_QUERY_K,
            "neighbors": NEIGHBOR_EXTRAS,
        }
    return {
        "top_k": COMFORT_TOP_K,
        "candidate_k": 24,
        "rerank_candidate_k": 24,
        "extras_budget": 4,
        "per_query_k": 3,
        "neighbors": 4,
    }
