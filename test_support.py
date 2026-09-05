"""
Shared helpers for API tests.

Every route resolves an actor, so a test client must carry an identity the
same way the browser does.
"""

import uuid

from fastapi.testclient import TestClient

from app_platform.auth.guest import GUEST_SESSION_HEADER


def new_guest_session() -> str:
    return f"test-{uuid.uuid4().hex}"


def api_client(app, session_id: str | None = None) -> TestClient:
    """
    TestClient that identifies itself as a guest on every request.

    Each client gets a fresh session so trial quotas from earlier tests (or
    earlier runs against the same dev database) cannot leak in.
    """
    return TestClient(
        app,
        headers={GUEST_SESSION_HEADER: session_id or new_guest_session()},
    )
