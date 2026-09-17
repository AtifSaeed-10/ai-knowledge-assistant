"""
Who is making this request.

One actor per request: either a guest session or a signed-in user. Ownership
rows and usage counters are keyed by (actor_type, actor_id), so the two tiers
share all downstream code.
"""

from __future__ import annotations

from dataclasses import dataclass

ACTOR_GUEST = "guest"
ACTOR_USER = "user"


@dataclass(frozen=True)
class RequestContext:
    actor_type: str
    actor_id: str
    email: str | None = None

    @property
    def is_guest(self) -> bool:
        return self.actor_type == ACTOR_GUEST

    @property
    def is_user(self) -> bool:
        return self.actor_type == ACTOR_USER

    @property
    def tier(self) -> str:
        return "guest" if self.is_guest else "free"


def guest_context(session_id: str) -> RequestContext:
    return RequestContext(actor_type=ACTOR_GUEST, actor_id=session_id)


def user_context(user_id: str, email: str | None = None) -> RequestContext:
    return RequestContext(actor_type=ACTOR_USER, actor_id=user_id, email=email)
