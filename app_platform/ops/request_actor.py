"""
The current request actor, for code that sits below the FastAPI dependency.

Set from get_request_context in the same thread as the route, so the LLM
router can attribute a failure without taking a Request object.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

from app_platform.auth.context import RequestContext

_actor: ContextVar[RequestContext | None] = ContextVar("docusage_actor", default=None)


def bind_actor(context: RequestContext | None) -> Token:
    return _actor.set(context)


def current_actor() -> RequestContext | None:
    return _actor.get()
