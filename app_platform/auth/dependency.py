"""
FastAPI dependency that resolves the request actor.

A valid Bearer token wins over a guest header, so a signed-in user whose
browser still holds a trial id is treated as the user.
"""

from __future__ import annotations

from fastapi import Header, Request

from app_platform import errors, settings
from app_platform.auth.context import RequestContext, guest_context, user_context
from app_platform.auth.guest import normalize_session_id
from app_platform.auth.supabase_jwt import TokenError, bearer_token, verify_token
from app_platform.ops.request_actor import bind_actor
from database.guest_store import ensure_guest_session
from database.user_store import upsert_user


def resolve_context(
    authorization: str | None,
    guest_session: str | None,
) -> RequestContext:
    """Identity resolution, independent of FastAPI so it is directly testable."""
    token = bearer_token(authorization)
    if token:
        if not settings.auth_enabled():
            raise errors.auth_required("Sign-in is not enabled on this server.")
        try:
            claims = verify_token(token)
        except TokenError as exc:
            raise errors.auth_required("Your session has expired. Sign in again.") from exc
        profile = upsert_user(str(claims["sub"]), claims.get("email"))
        return user_context(profile["user_id"], profile.get("email"))

    if not settings.GUEST_TRIAL_ENABLED:
        raise errors.auth_required("Sign in to continue.")

    session_id = normalize_session_id(guest_session)
    if not session_id:
        raise errors.auth_required(
            "Missing session. Reload the page to start your free trial."
        )
    ensure_guest_session(session_id)
    return guest_context(session_id)


def get_request_context(
    request: Request,
    authorization: str | None = Header(default=None),
    x_guest_session: str | None = Header(default=None),
) -> RequestContext:
    context = resolve_context(authorization, x_guest_session)
    request.state.actor = context
    bind_actor(context)
    return context
