"""
Answer planning: map user intent to briefing components before generation.

Does not change retrieval directly; informs the prompt and optional sub-queries.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from conversation_query import (
    INTENT_COMPARISON,
    INTENT_DEFINITION,
    INTENT_EXAMPLE,
    INTENT_EXPLANATION,
    INTENT_HOW,
    INTENT_LISTING,
    INTENT_MIXED,
    INTENT_WHY,
    TurnAnalysis,
)

# Soft word budget for briefing-style answers.
BRIEFING_WORD_MIN = 120
BRIEFING_WORD_MAX = 240
MAX_CITATION_MARKERS = 5


@dataclass(frozen=True)
class AnswerComponent:
    role: str
    label: str
    required: bool = False
    max_sentences: int = 2


@dataclass
class AnswerPlan:
    components: list[AnswerComponent] = field(default_factory=list)
    sub_queries: list[str] = field(default_factory=list)
    briefing: bool = False


_COMPONENT_LIBRARY: dict[str, list[AnswerComponent]] = {
    INTENT_DEFINITION: [
        AnswerComponent("definition", "what it is", required=True, max_sentences=2),
        AnswerComponent("mechanism", "how it works", max_sentences=2),
        AnswerComponent("types", "types or categories", max_sentences=1),
        AnswerComponent("example", "document example", max_sentences=1),
    ],
    INTENT_EXPLANATION: [
        AnswerComponent("overview", "overview", required=True, max_sentences=2),
        AnswerComponent("mechanism", "how or why it works", max_sentences=2),
        AnswerComponent("example", "document example", max_sentences=1),
    ],
    INTENT_WHY: [
        AnswerComponent("reason", "purpose, cause, or usefulness", required=True, max_sentences=2),
        AnswerComponent("example", "supporting example", max_sentences=1),
    ],
    INTENT_HOW: [
        AnswerComponent("process", "steps or mechanism", required=True, max_sentences=3),
        AnswerComponent("example", "supporting example", max_sentences=1),
    ],
    INTENT_LISTING: [
        AnswerComponent("list", "explicit list of items", required=True, max_sentences=4),
    ],
    INTENT_EXAMPLE: [
        AnswerComponent("example", "concrete example from the document", required=True, max_sentences=2),
    ],
    INTENT_COMPARISON: [
        AnswerComponent("comparison", "supported comparison points", required=True, max_sentences=4),
    ],
    INTENT_MIXED: [
        AnswerComponent("parts", "each supported part of the request", required=True, max_sentences=4),
    ],
}


def plan_answer(
    question: str,
    search_query: str,
    analysis: TurnAnalysis | None,
) -> AnswerPlan:
    """Build an answer plan from turn analysis."""
    intent = analysis.intent if analysis else "factual"
    subject = (analysis.subject if analysis else "") or search_query or question
    subject = subject.strip()

    components = list(_COMPONENT_LIBRARY.get(intent, []))
    briefing = intent in {
        INTENT_DEFINITION,
        INTENT_EXPLANATION,
        INTENT_MIXED,
        INTENT_COMPARISON,
    }

    sub_queries: list[str] = []
    if briefing and subject:
        role_queries = {
            "definition": f"What is {subject}?",
            "types": f"What are the types of {subject}?",
            "example": f"Example of {subject}",
            "mechanism": f"How does {subject} work?",
            "process": f"How does {subject} work step by step?",
            "reason": f"Why is {subject} used?",
            "overview": f"Explain {subject}",
        }
        for component in components:
            query = role_queries.get(component.role)
            if query:
                sub_queries.append(query)
        seen: set[str] = set()
        unique: list[str] = []
        for item in sub_queries:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        sub_queries = unique[:4]

    return AnswerPlan(components=components, sub_queries=sub_queries, briefing=briefing)


def format_plan_for_prompt(plan: AnswerPlan) -> str:
    if not plan.components:
        return ""

    lines = [
        "Answer plan (internal; do not mention this section to the user):",
        f"Target length: {BRIEFING_WORD_MIN}-{BRIEFING_WORD_MAX} words total.",
        f"Use at most {MAX_CITATION_MARKERS} citation markers.",
    ]

    if plan.briefing:
        lines.extend(
            [
                "Format as a concise research briefing:",
                "**Overview** — required if definition/overview is supported.",
                "**Key points** — 2-4 short bullets for mechanism, types, or algorithms ONLY if supported.",
                "**Example** — one sentence only if the document gives an example.",
                "Omit any section with no supporting passage. Do not repeat the same idea twice.",
            ]
        )

    for component in plan.components:
        req = "required" if component.required else "include only if supported"
        lines.append(
            f"- {component.label} ({req}; max {component.max_sentences} sentence"
            f"{'s' if component.max_sentences != 1 else ''})"
        )

    lines.extend(
        [
            "Write in your own words. Paraphrase every claim.",
            "Verbatim wording belongs ONLY inside [E#:\"...\"] markers (8-15 words each).",
            "Never paste long block quotes or multi-sentence quotations in the prose.",
        ]
    )
    return "\n".join(lines)
