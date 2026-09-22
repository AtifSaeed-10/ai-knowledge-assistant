"""Stream status frames. The UI shows these; they never become answer text."""

from __future__ import annotations

import json

STATUS_START = "__STATUS__"
STATUS_END = "__END_STATUS__"

STEP_DOCUMENTS = "documents"
STEP_WEB = "web"
STEP_READING = "reading"
STEP_WRITING = "writing"
STEP_DONE = "done"

STATUS_CHECKING_DOCUMENTS = "Checking your documents…"
STATUS_SEARCHING_WEB = "Nothing in your documents. Searching the web…"
STATUS_READING_SOURCES = "Reading sources…"
STATUS_WRITING_WEB = "Writing answer…"
STATUS_WRITING_DOCUMENTS = "Writing from your documents…"


def status_frame(step: str, message: str = "") -> str:
    payload = json.dumps(
        {"step": step, "message": message},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"{STATUS_START}{payload}{STATUS_END}"
