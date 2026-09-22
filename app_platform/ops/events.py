"""
Write operator events without ever breaking a user request.

Messages are short and redacted. Prompts, PDFs, and answers stay out.
"""

from __future__ import annotations

from typing import Any

from app_platform.auth.context import RequestContext
from app_platform.ops.request_actor import current_actor
from database.event_store import record_event
from llm.sanitize import redact_secrets

_MESSAGE_MAX = 240
_SKIP_STATUS = {401, 403, 404}
_RECORD_STATUS = {400, 402, 409, 413, 422, 429, 500, 502, 503, 504}


def _clip(message: str | None) -> str | None:
    text = redact_secrets(message or "").strip()
    if not text:
        return None
    if len(text) > _MESSAGE_MAX:
        return text[: _MESSAGE_MAX - 1] + "…"
    return text


def _actor_fields(actor: RequestContext | None) -> dict[str, str | None]:
    if actor is None:
        actor = current_actor()
    if actor is None:
        return {"actor_type": None, "actor_id": None}
    return {"actor_type": actor.actor_type, "actor_id": actor.actor_id}


def record_safe(**kwargs: Any) -> None:
    try:
        record_event(**kwargs)
    except Exception:
        return


def record_llm_event(
    *,
    provider: str | None,
    category: str | None,
    message: str | None = None,
    actor: RequestContext | None = None,
) -> None:
    record_safe(
        kind="llm",
        route="/chat",
        provider=provider,
        category=category,
        message=_clip(message or category),
        **_actor_fields(actor),
    )


def record_index_failure(document_id: str, message: str) -> None:
    actor_type = None
    actor_id = None
    try:
        from database.document_store import get_document

        document = get_document(document_id)
        if document:
            actor_type = document.get("owner_type")
            actor_id = document.get("owner_id")
    except Exception:
        pass
    record_safe(
        kind="index",
        route="/upload",
        category="index_failed",
        message=_clip(message),
        document_id=document_id,
        actor_type=actor_type,
        actor_id=actor_id,
    )


def record_http_exception(
    path: str,
    status_code: int,
    detail: Any,
    actor: RequestContext | None = None,
) -> None:
    if status_code in _SKIP_STATUS:
        return
    if status_code not in _RECORD_STATUS and status_code < 500:
        return

    code = None
    message = None
    if isinstance(detail, dict):
        code = detail.get("code")
        message = detail.get("message") or str(detail)
    elif detail is not None:
        message = str(detail)

    kind = "quota" if status_code == 402 or code == "QUOTA_EXCEEDED" else "http"
    record_safe(
        kind=kind,
        route=(path or "")[:120] or None,
        category=code or f"http_{status_code}",
        status_code=status_code,
        message=_clip(message),
        **_actor_fields(actor),
    )


def record_unanswered(
    *,
    question: str,
    answer: str,
    actor: RequestContext | None = None,
    route: str = "/chat",
    provider: str | None = None,
    model: str | None = None,
) -> bool:
    """Log a blanket 'couldn't answer' so the operator can see the failure kind."""
    from app_platform.ops.unanswered import unanswered_category, unanswered_label

    category = unanswered_category(answer)
    if not category:
        return False
    clipped_question = _clip(question) or unanswered_label(category)
    record_safe(
        kind="unanswered",
        route=(route or "/chat")[:120],
        provider=provider,
        category=category,
        message=clipped_question,
        **_actor_fields(actor),
    )
    return True


def record_answer(
    *,
    question: str,
    actor: RequestContext | None = None,
    route: str = "/chat",
    provider: str | None = None,
    model: str | None = None,
) -> None:
    """Log which LLM produced a grounded answer. Never stores the answer text."""
    if not provider:
        return
    detail = " ".join(part for part in (model, _clip(question)) if part)
    record_safe(
        kind="answer",
        route=(route or "/chat")[:120],
        provider=provider,
        category="answered",
        message=_clip(detail),
        **_actor_fields(actor),
    )
