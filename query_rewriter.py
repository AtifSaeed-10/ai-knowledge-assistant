from llm_service import generate_response
from conversation_query import (
    TurnAnalysis,
    compose_followup_query,
    extract_enumerated_items,
    extract_focus_subject,
    format_history_for_rewrite,
    last_assistant_text,
)


_REWRITE_PROMPT = """
You rewrite follow-up questions into standalone search questions for a document Q&A system.

Return the current user question UNCHANGED when:
- it is already a complete standalone question, or
- it introduces a new topic that does not depend on earlier turns.

Otherwise resolve references using the conversation:
- pronouns and demonstratives (it, this, that, they)
- ordinals (the first one, the second, the previous point)
- brief requests that omit the topic (why?, how?, an example, types, simpler)

Use the latest assistant answer to resolve ordered items and named entities.
The rewritten question must stay on the current subject unless the user clearly changed topic.
For type/category questions, rewrite as types/categories OF the current subject, not a parent concept.
Preserve the user's intent in the rewritten question (why / how / example / types / simplify / compare).
Do not answer the user.
Do not add facts that were not mentioned.
Return only the standalone question, no quotes or preamble.
Keep it under 30 words.

Current subject: {subject}
Extracted list items from the last answer: {items}

Conversation:
{conversation}

Current user question:
{question}

Standalone question:
""".strip()


def _looks_like_search_question(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    if stripped.endswith("?"):
        return True
    lowered = stripped.lower()
    return lowered.startswith(
        (
            "what",
            "why",
            "how",
            "who",
            "when",
            "where",
            "which",
            "explain",
            "define",
            "compare",
            "list",
            "summar",
            "give",
            "describe",
            "show",
            "key",
            "example",
            "types",
        )
    )


def _clean_rewritten(text: str, original: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return original
    if cleaned[0] in {"\"", "'"} and cleaned[-1] == cleaned[0]:
        cleaned = cleaned[1:-1].strip()
    if len(cleaned.split()) > 30 or len(cleaned) > 220:
        return original
    lowered = cleaned.lower()
    if lowered.startswith(("answer:", "the answer", "based on")):
        return original
    if _looks_like_search_question(original) and not _looks_like_search_question(cleaned):
        return original
    return cleaned or original


def rewrite_query(question, history, analysis: TurnAnalysis | None = None):
    """
    Converts follow-up questions into standalone questions.
    Callers should skip this when analysis.needs_rewrite is False.
    Prefer a deterministic composition; fall back to the LLM rewriter.
    """

    if not history:
        return question

    composed = compose_followup_query(question, history, analysis)
    if composed:
        cleaned = _clean_rewritten(composed, question)
        if cleaned.strip() and cleaned.strip().lower() != str(question or "").strip().lower():
            return cleaned

    conversation = format_history_for_rewrite(history)
    subject = (analysis.subject if analysis and analysis.subject else None) or extract_focus_subject(history)
    items = extract_enumerated_items(last_assistant_text(history))
    intent_line = ""
    if analysis is not None:
        intent_line = (
            f"\nDetected intent: {analysis.intent}. "
            f"Relation: {analysis.relation}.\n"
        )

    prompt = _REWRITE_PROMPT.format(
        conversation=conversation,
        question=question,
        subject=subject or "(unknown — do not invent a topic)",
        items=", ".join(items) if items else "(none extracted)",
    )
    if intent_line:
        prompt = prompt.replace(
            "Current user question:",
            intent_line + "Current user question:",
        )

    rewritten_question = generate_response(prompt)
    return _clean_rewritten(rewritten_question, question)
