"""
Anonymous trial sessions.

The client generates a UUID and sends it as X-Guest-Session. It is a trial
bucket, not a credential: it grants access only to rows created under the
same id, and the trial limits are small enough that forging one gains
nothing a new browser profile would not.
"""

from __future__ import annotations

import re

_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

GUEST_SESSION_HEADER = "X-Guest-Session"


def normalize_session_id(raw: str | None) -> str | None:
    """Return a safe session id, or None when the header is missing/invalid."""
    value = (raw or "").strip()
    if not value or not _SESSION_RE.match(value):
        return None
    return value
