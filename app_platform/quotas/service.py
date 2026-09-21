"""
Quota checks and usage recording.

Checks run in the API shell before any retrieval work starts, so a blocked
request never reaches the RAG pipeline or the LLM provider.
"""

from __future__ import annotations

from typing import Any

from app_platform import errors, settings
from app_platform.auth.context import RequestContext
from app_platform.quotas.limits import (
    GUEST_PERIOD,
    RESOURCE_PDFS,
    RESOURCE_QUESTIONS,
    RESOURCE_WEB_QUESTIONS,
    limits_for,
)
from database import usage_store
from database.document_store import count_documents_for_owner
from database.guest_store import (
    get_guest_session,
    increment_guest_question_count,
    increment_guest_web_question_count,
)


def _period_for(context: RequestContext) -> str:
    return GUEST_PERIOD if context.is_guest else usage_store.current_period()


def questions_used(context: RequestContext) -> int:
    if context.is_guest:
        session = get_guest_session(context.actor_id)
        return int((session or {}).get("question_count") or 0)
    return usage_store.get_question_count(
        context.actor_type,
        context.actor_id,
        _period_for(context),
    )


def web_lookups_used(context: RequestContext) -> int:
    if context.is_guest:
        session = get_guest_session(context.actor_id)
        return int((session or {}).get("web_question_count") or 0)
    return usage_store.get_web_question_count(
        context.actor_type,
        context.actor_id,
        _period_for(context),
    )


def pdfs_used(context: RequestContext) -> int:
    """Live document count, so deleting a PDF frees a slot."""
    return count_documents_for_owner(context.actor_type, context.actor_id)


def usage_summary(context: RequestContext) -> dict[str, Any]:
    from app_platform.auth.admin import is_admin

    limits = limits_for(context)
    admin = is_admin(context)
    return {
        "tier": context.tier,
        "actor_type": context.actor_type,
        "pdfs_used": pdfs_used(context),
        "pdfs_limit": 0 if admin else limits.max_pdfs,
        "questions_used": questions_used(context),
        "questions_limit": 0 if admin else limits.max_questions,
        "questions_window": limits.questions_window,
        "web_questions_used": web_lookups_used(context),
        "web_questions_limit": 0 if admin else limits.max_web_questions,
        "max_pdf_mb": settings.QUOTA_MAX_PDF_MB,
        "auth_available": settings.auth_enabled(),
        "admin": admin,
        "unlimited": admin,
    }


def check_upload_allowed(context: RequestContext) -> None:
    from app_platform.auth.admin import is_admin

    if is_admin(context):
        return
    limits = limits_for(context)
    used = pdfs_used(context)
    if used < limits.max_pdfs:
        return
    if context.is_guest:
        message = (
            f"The free trial covers {limits.max_pdfs} document. "
            "Sign in to add more — still free."
        )
    else:
        message = (
            f"You have reached your {limits.max_pdfs} document limit. "
            "Delete a document to upload another."
        )
    raise errors.quota_exceeded(
        message,
        limit=limits.max_pdfs,
        used=used,
        resource=RESOURCE_PDFS,
        upgrade_hint="sign_in" if context.is_guest else "delete_document",
    )


def check_question_allowed(context: RequestContext) -> None:
    from app_platform.auth.admin import is_admin

    if is_admin(context):
        return
    limits = limits_for(context)
    used = questions_used(context)
    if used < limits.max_questions:
        return
    if context.is_guest:
        message = (
            f"You have used all {limits.max_questions} trial questions. "
            "Sign in to save this document and keep going — still free."
        )
    else:
        message = (
            f"You have used all {limits.max_questions} questions for this month. "
            "Your allowance resets next month."
        )
    raise errors.quota_exceeded(
        message,
        limit=limits.max_questions,
        used=used,
        resource=RESOURCE_QUESTIONS,
        upgrade_hint="sign_in" if context.is_guest else "wait_for_reset",
    )


def check_upload_size(size_bytes: int | None) -> None:
    limit = settings.max_pdf_bytes()
    if size_bytes is not None and size_bytes > limit:
        raise errors.payload_too_large(
            f"That PDF is larger than the {settings.QUOTA_MAX_PDF_MB} MB limit.",
            limit_mb=settings.QUOTA_MAX_PDF_MB,
        )


def record_question(context: RequestContext) -> None:
    """Count one answered question against the actor's allowance."""
    from app_platform.auth.admin import is_admin

    if is_admin(context):
        return
    if context.is_guest:
        increment_guest_question_count(context.actor_id)
        return
    usage_store.increment_question_count(
        context.actor_type,
        context.actor_id,
        _period_for(context),
    )


def web_lookup_allowed(context: RequestContext) -> bool:
    from app_platform.auth.admin import is_admin

    if is_admin(context):
        return True
    limits = limits_for(context)
    return web_lookups_used(context) < limits.max_web_questions


def web_lookup_limit_message(context: RequestContext) -> str:
    limits = limits_for(context)
    used = web_lookups_used(context)
    if context.is_guest:
        return (
            f"You've used all {limits.max_web_questions} trusted-site lookups "
            f"in this trial ({used}/{limits.max_web_questions}). "
            "Sign in to get 100 a month — still free. Your PDFs still come first."
        )
    return (
        f"You've used all {limits.max_web_questions} trusted-site lookups "
        "for this month. Your allowance resets next month."
    )


def record_web_lookup(context: RequestContext) -> None:
    """Count one live trusted-site search against the actor's web allowance."""
    from app_platform.auth.admin import is_admin

    if is_admin(context):
        return
    if context.is_guest:
        increment_guest_web_question_count(context.actor_id)
        return
    usage_store.increment_web_question_count(
        context.actor_type,
        context.actor_id,
        _period_for(context),
    )
