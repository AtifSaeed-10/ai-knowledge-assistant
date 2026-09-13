"""
Operator access for the private operations dashboard.

The allowlist is server-side. Hiding /admin in the UI is not the lock.
"""

from __future__ import annotations

from fastapi import Depends

from app_platform import errors, settings
from app_platform.auth.context import RequestContext
from app_platform.auth.dependency import get_request_context


def admin_emails() -> set[str]:
    return {email.lower() for email in settings.ADMIN_EMAILS if email}


def is_admin(context: RequestContext) -> bool:
    if not context.is_user:
        return False
    email = (context.email or "").strip().lower()
    return bool(email) and email in admin_emails()


def require_admin(
    context: RequestContext = Depends(get_request_context),
) -> RequestContext:
    if not context.is_user:
        raise errors.auth_required("Sign in to continue.")
    if not is_admin(context):
        raise errors.forbidden("You do not have access to this resource.")
    return context
