"""
Answer planning: map user intent to briefing components before generation.

Does not change retrieval directly; informs the prompt and optional sub-queries.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from query_retrieval import parse_section_ref
from conversation_query import (
    INTENT_COMPARISON,
    INTENT_DEFINITION,
    INTENT_EXAMPLE,
    INTENT_EXPLANATION,
    INTENT_HOW,
    INTENT_KEY_POINTS,
    INTENT_LISTING,
    INTENT_MIXED,
    INTENT_SUMMARY,
    INTENT_WHY,
    TurnAnalysis,
    split_conjunctive_topics,
)
from wide_recall import is_wide_recall_question, lexical_probe_queries

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
    multi_topic: bool = False
    wide_recall: bool = False


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
    INTENT_SUMMARY: [
        AnswerComponent(
            "summary",
            "synthesize a short summary from the passages in context — do not look for a heading titled Summary",
            required=True,
            max_sentences=6,
        ),
    ],
    INTENT_KEY_POINTS: [
        AnswerComponent(
            "key_points",
            "3-5 bullets synthesized from the passages in context — do not look for a pre-written key-points list",
            required=True,
            max_sentences=5,
        ),
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
    topics = split_conjunctive_topics(question)

    components = list(_COMPONENT_LIBRARY.get(intent, []))
    if len(topics) >= 2 and not components:
        components = list(_COMPONENT_LIBRARY[INTENT_MIXED])
    briefing = intent in {
        INTENT_DEFINITION,
        INTENT_EXPLANATION,
        INTENT_MIXED,
        INTENT_COMPARISON,
        INTENT_SUMMARY,
        INTENT_KEY_POINTS,
    }

    sub_queries: list[str] = []
    section = parse_section_ref(question) or parse_section_ref(search_query)
    if section:
        sub_queries.append(f"{section[0]} {section[1]}")
    if len(topics) >= 2:
        sub_queries.extend(topics)
        briefing = True
    probes = lexical_probe_queries(question)
    sub_queries.extend(probes)
    wide = is_wide_recall_question(question, intent) or len(topics) >= 2
    if briefing and subject and len(topics) < 2 and not wide:
        role_queries = {
            "definition": f"What is {subject}?",
            "types": f"What are the types of {subject}?",
            "example": f"Example of {subject}",
            "mechanism": f"How does {subject} work?",
            "process": f"How does {subject} work step by step?",
            "reason": f"Why is {subject} used?",
            "overview": f"Explain {subject}",
            "summary": f"Overview of {subject}",
            "key_points": f"Key points of {subject}",
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
    sub_queries = unique[:6]

    return AnswerPlan(
        components=components,
        sub_queries=sub_queries,
        briefing=briefing or wide,
        multi_topic=len(topics) >= 2,
        wide_recall=wide,
    )


def format_plan_for_prompt(plan: AnswerPlan) -> str:
    if not plan.components and not plan.wide_recall:
        return ""

    word_max = 360 if plan.wide_recall else BRIEFING_WORD_MAX
    marker_max = 8 if plan.wide_recall else MAX_CITATION_MARKERS

    lines = [
        "Answer plan (internal; do not mention this section to the user):",
        f"Target length: {BRIEFING_WORD_MIN}-{word_max} words total.",
        f"Use at most {marker_max} citation markers.",
    ]

    if plan.wide_recall:
        lines.append(
            "This question spans a story or a long stretch of the document. "
            "Use every supporting passage, including later pages. Do not refuse "
            "a later event because an earlier scene is also in context. If the "
            "passages only cover part of the arc, answer that part fully and "
            "say what is missing."
        )
        lines.append(
            "Write a clear narrative briefing: short paragraphs or bullets. "
            "Cover the opening, the turning point, and the later outcome when "
            "those parts are in the passages. Do not pad with a textbook template."
        )

    if plan.briefing and not plan.wide_recall:
        lines.extend(
            [
                "Format as a concise research briefing:",
                "**Overview** — required if definition/overview is supported.",
                "**Key points** — 2-4 short bullets for mechanism, types, or algorithms ONLY if supported.",
                "**Example** — one sentence only if the document gives an example.",
                "Omit any section with no supporting passage. Do not repeat the same idea twice.",
            ]
        )
    if plan.multi_topic:
        lines.append(
            "This is a multi-topic request. Answer each topic from the passages "
            "that support it. If a topic has no supporting passage, say so for "
            "that topic only — do not drop the other topics."
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
