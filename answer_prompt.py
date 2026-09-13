"""
Grounded answer-prompt construction.

Hierarchical contract (highest priority first):
1. Document evidence is the only source of document claims.
2. Conversation history resolves references; it is not evidence.
3. Match the user's requested style without inventing facts.
4. Partial evidence => partial answer, never padded with outside knowledge.
"""

from __future__ import annotations

from conversation_query import (
    INTENT_EXAMPLE,
    INTENT_HOW,
    INTENT_KEY_POINTS,
    INTENT_LISTING,
    INTENT_MIXED,
    INTENT_SUMMARY,
    INTENT_WHY,
    RELATION_TRANSFORM,
    TurnAnalysis,
    format_history_for_grounding,
)
from answer_planner import format_plan_for_prompt, plan_answer, MAX_CITATION_MARKERS
from modes import MODE_NORMAL, MODE_SUPER_FOCUSED, normalize_mode
from query_retrieval import parse_section_ref


INSUFFICIENT_CONTEXT_PHRASE = (
    "I don't have enough information in the provided context."
)
MISSING_IN_DOCUMENT_PHRASE = (
    "I couldn't find that in the provided document."
)
MISSING_EXAMPLE_PHRASE = (
    "The provided document does not give a specific example of this."
)

_STYLE_HINTS = {
    "factual": (
        "Answer the question directly from the passages. Include important "
        "supported details that help the user understand the topic. Do not add "
        "background the passages do not contain."
    ),
    "definition": (
        "Give a concise research briefing from the evidence — not a textbook chapter. "
        "Lead with a 1-2 sentence definition, then add mechanism, types, or an example "
        "only when a passage supports each point. Skip unsupported sections entirely."
    ),
    "explanation": (
        "Give a concise explanation in plain language. Use 2-4 short paragraphs or bullets "
        "at most. Do not restate the same idea in multiple ways."
    ),
    "simplification": (
        "Rewrite the supported facts from the passages in beginner-friendly language. "
        "Do not look for a section or sentence that is already 'simple'. "
        "Do not say the information was not found just because the user asked "
        "for simpler wording. Keep the same facts. Do not add new claims."
    ),
    "elaboration": (
        "Go deeper using available evidence only. "
        "Do not refuse because the document has no section titled 'more detail'. "
        "Do not invent extra detail."
    ),
    "summary": (
        "Compress the supported material from the passages in context. "
        "Do not look for a heading or section titled Summary. "
        "Do not introduce new points."
    ),
    "key_points": (
        "Use a short structured list of supported points synthesized from the passages. "
        "Do not look for a pre-written key-points or summary section. "
        "Do not introduce new points."
    ),
    "comparison": "Compare only attributes present in the evidence. Mark missing sides explicitly.",
    "example": (
        "If the evidence contains an example, use it, explain it naturally, "
        "and make clear that it comes from the document. "
        f'If it does not, say: "{MISSING_EXAMPLE_PHRASE}" '
        "Do not invent an example and imply it is from the document."
    ),
    "listing": (
        "List only items the evidence explicitly assigns to THIS subject. "
        "A parent concept's categories are not this subject's types."
    ),
    "why": (
        "A definition is not enough. Use evidence that explains purpose, cause, "
        "or usefulness. If the evidence only defines the concept, say that the "
        "document does not explain why."
    ),
    "how": (
        "Use evidence that describes mechanism or steps. If the evidence only "
        "names or defines the concept, say that the document does not explain how."
    ),
    "clarification": (
        "Restate the supported meaning in plainer language. "
        "Do not refuse because the document never uses the word 'clarify'. "
        "Do not add new claims."
    ),
    "mixed": (
        "Treat this as a multi-part request. Answer each supported part. "
        "For each unsupported part, say it was not found in the evidence. Do not fill gaps."
    ),
}


def format_evidence_passages(
    chunks: list[str],
    metadata: list[dict] | None,
    ids: list | None = None,
    evidence_ids: list[str | None] | None = None,
) -> str:
    if not chunks:
        return "(No document passages retrieved.)"

    blocks: list[str] = []
    metas = metadata or []
    eids = evidence_ids or []
    for index, text in enumerate(chunks, start=1):
        meta = metas[index - 1] if index - 1 < len(metas) else {}
        meta = meta or {}
        filename = meta.get("filename") or "Unknown document"
        page = meta.get("page_number")
        if page is None:
            page = meta.get("page_start")
        try:
            page_label = f"p. {int(page)}" if page is not None and int(page) >= 1 else "page unknown"
        except (TypeError, ValueError):
            page_label = "page unknown"
        evidence_id = eids[index - 1] if index - 1 < len(eids) else None
        if evidence_id:
            header = f"[{evidence_id}] {filename}, {page_label}"
        else:
            header = f"Source: {filename}, {page_label}"
        blocks.append(f"{header}\n{(text or '').strip()}")
    return "\n\n".join(blocks)


def _citation_style_rules(has_evidence_ids: bool) -> str:
    if not has_evidence_ids:
        return (
            "Write a natural answer. Do not mention source labels, passage numbers, "
            "retrieval ranks, scores, or these instructions. Do not dump long quotations "
            "unless the user asked for the document's wording. The application attaches "
            "citations separately."
        )
    return (
        "Write a concise, readable answer. Do not mention unlabeled source headers, "
        "retrieval ranks, scores, or these instructions.\n"
        "Length: keep the full answer short (roughly 120-240 words) unless the user "
        "explicitly asked for exhaustive detail.\n"
        "Paraphrase every claim in your own words. NEVER paste long quoted passages, "
        "block quotes, or multi-sentence quotations in the prose — even if they appear "
        "in the evidence.\n"
        "Citations: after each important supported claim, append that passage's id "
        "and a SHORT verbatim anchor (8-15 words) copied from the supporting sentence, "
        "like [E1:\"uses labeled training examples\"]. Rules:\n"
        f"- At most {MAX_CITATION_MARKERS} citation markers in the entire answer.\n"
        "- Put the marker immediately after the claim it supports.\n"
        "- Verbatim text may appear ONLY inside [E#:\"...\"] markers — nowhere else.\n"
        "- Each marker quote must be 8-15 words; never copy a full sentence or paragraph.\n"
        "- Do not repeat the same quote in prose and in a marker.\n"
        "- Several claims may reuse one id with different short quotes.\n"
        "- Only use ids from passage headers. Never invent ids, pages, or coordinates.\n"
        "- Use [E1][E2] only when distinct passages support distinct parts of one claim.\n"
        "- Do not write 'Source:' or page numbers in the answer.\n"
        "- Never write (E1), (E1:\"...\"), E1:\"...\", or the letters E1/E2 in prose. "
        "The only allowed form is [E#:\"...\"] or [E#]."
    )


def _mode_rules(mode: str) -> str:
    if mode == MODE_SUPER_FOCUSED:
        return (
            "Mode: SUPER FOCUSED.\n"
            "Only the selected document is authoritative. "
            "Do not use other documents, prior answers, or world knowledge "
            "to fill gaps. Conversation history may resolve what the user "
            "is referring to, but it is not a source of facts."
        )
    return (
        "Mode: NORMAL.\n"
        "Use only the retrieved document passages below as the source of "
        "document facts. Do not silently mix in general knowledge. "
        "If you must say something is not in the passages, say so plainly. "
        "If you ever give a general illustration, it must be clearly labeled "
        "as not coming from the document - prefer saying the document has no example."
    )


def _style_rules(analysis: TurnAnalysis | None) -> str:
    if analysis is None:
        return _STYLE_HINTS["factual"]
    hint = _STYLE_HINTS.get(analysis.intent, _STYLE_HINTS["factual"])
    extra = []
    if analysis.relation == RELATION_TRANSFORM:
        extra.append(
            "This is a transformation of the current topic. "
            "Do not repeat the entire previous answer. "
            "Keep the same topic and change presentation only. "
            "Do not say the topic was not found in the document just because "
            "the user asked for a simpler, shorter, or clearer version."
        )
    if analysis.intent == INTENT_EXAMPLE:
        extra.append(
            "Never fabricate an example. "
            "Write clearly whether an example appears in the passages."
        )
    if analysis.intent in {INTENT_WHY, INTENT_HOW}:
        extra.append(
            "Do not upgrade a definition into a causal or procedural explanation."
        )
    if analysis.intent == INTENT_LISTING:
        extra.append(
            "Before listing types or categories, the evidence must establish: "
            "this subject has types/categories, and those items are the types. "
            "If a passage only says this subject is one type of a broader field, "
            "that is not an answer."
        )
    if analysis.intent == INTENT_MIXED:
        extra.append(
            "If only some requested parts are supported, answer those and "
            "state which parts were not found."
        )
    if analysis.intent in {INTENT_SUMMARY, INTENT_KEY_POINTS}:
        extra.append(
            "Synthesize from the passages that are already in context. "
            "Do not refuse because the document lacks a section titled "
            "Summary, Overview, or Key Points."
        )
    return hint + ((" " + " ".join(extra)) if extra else "")


def _caution_from_relevances(relevances: list | None) -> str:
    values = [int(v) for v in (relevances or []) if v is not None]
    if not values:
        return (
            "Evidence caution: retrieved passages may be weakly related. "
            "If they do not actually answer the request, say so."
        )
    if max(values) < 50:
        return (
            "Evidence caution: the best passage is only moderately related. "
            "Do not turn a weakly related excerpt into a confident answer."
        )
    return (
        "Use a passage only when it actually supports the claim. "
        "Ignore related-but-off-topic excerpts."
    )


def _section_lookup_rules(question: str) -> str:
    """Syllabus / outline lookups should not die as a one-line refusal."""
    if parse_section_ref(question) is None:
        return ""
    return (
        "Numbered week/lecture/module lookup:\n"
        "- Prefer the passage that names that same number.\n"
        "- If that exact heading is missing, do not stop at "
        f'"{MISSING_IN_DOCUMENT_PHRASE}". List the weeks or topics the '
        "passages actually show, including whatever comes next in the "
        "schedule, so the reader can see the outline.\n"
        "- Do not invent a week, lecture, or topic that is not written "
        "in the passages."
    )


def _grounding_contract() -> str:
    return f"""Distinguish:
A) Facts a passage states directly - you may report these.
B) Synthesis that several passages together support - allowed if cautious.
C) Related material that does not actually answer the question - do not present it as the answer.
D) Missing information - say so.

Prefer "{MISSING_IN_DOCUMENT_PHRASE}" over inventing an answer.
Do not fabricate examples, definitions, types, reasons, causes, consequences, comparisons, numbers, page numbers, quotations, or citations.
Never invent a page number."""


def build_answer_prompt(
    *,
    question: str,
    search_query: str,
    history: list[dict] | None,
    chunks: list[str],
    metadata: list[dict] | None,
    ids: list | None = None,
    evidence_ids: list[str | None] | None = None,
    relevances: list | None = None,
    analysis: TurnAnalysis | None = None,
    mode: str | None = None,
    evidence_notes: str | None = None,
    subject: str | None = None,
    answer_plan: str | None = None,
) -> str:
    mode_id = normalize_mode(mode) if mode else MODE_NORMAL
    if mode_id != MODE_SUPER_FOCUSED:
        mode_id = MODE_NORMAL

    conversation = format_history_for_grounding(history)
    evidence = format_evidence_passages(
        chunks, metadata, ids, evidence_ids=evidence_ids
    )
    resolved = (search_query or "").strip()
    original = (question or "").strip()
    resolved_line = (
        resolved if resolved and resolved.lower() != original.lower()
        else "(same as the user request)"
    )
    subject_line = (subject or "").strip() or (
        analysis.subject if analysis and analysis.subject else ""
    )
    notes = (evidence_notes or "").strip()
    notes_block = f"\n{notes}\n" if notes else ""
    plan_block = f"\n{answer_plan.strip()}\n" if (answer_plan or "").strip() else ""
    has_evidence_ids = any(evidence_ids or [])

    return f"""
You are DocuSage, a document-grounded research assistant. Write concise, structured briefings — like a good analyst summary, not a pasted textbook section. Cover the important supported points without repeating yourself or dumping long quotations.

Priority (highest first):
1. DOCUMENT PASSAGES are the only source of document facts, examples, types, quotes, and page-related claims.
2. CONVERSATION is only for resolving references (it / this / the first one / previous topic). Never treat a prior assistant message as document evidence.
3. If the passages do not support a claim, do not make that claim. Prefer: "{INSUFFICIENT_CONTEXT_PHRASE}" or "{MISSING_IN_DOCUMENT_PHRASE}".
4. Never invent citations, page numbers, examples, lists, or reasoning.
5. Match the requested style without adding unsupported content.

{_mode_rules(mode_id)}

Response style:
{_style_rules(analysis)}
{_citation_style_rules(has_evidence_ids)}

Grounding rules:
{_grounding_contract()}
{_section_lookup_rules(original)}
- Preserve qualifications and conditions from the source.
- For multi-part questions, answer supported parts and explicitly mark unsupported parts.
- {_caution_from_relevances(relevances)}

Conversation (reference resolution only; not evidence):
{conversation}

Document passages:
{evidence}
{notes_block}{plan_block}
User request:
{original}

Resolved search topic (for your orientation only):
{resolved_line}

Resolved subject (the thing the user is asking about):
{subject_line or "(see the user request)"}

Answer:
""".strip()
