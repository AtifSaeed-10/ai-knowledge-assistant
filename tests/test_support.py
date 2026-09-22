"""
Shared helpers for API tests.

Every route resolves an actor, so a test client must carry an identity the
same way the browser does.
"""

import base64
import hashlib
import hmac
import json
import time
import uuid

from fastapi.testclient import TestClient

from app_platform.auth.guest import GUEST_SESSION_HEADER

TEST_JWT_SECRET = "unit-test-jwt-secret"


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


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def make_access_token(
    subject: str,
    email: str | None = None,
    *,
    expires_in: int = 3600,
    secret: str = TEST_JWT_SECRET,
) -> str:
    """Mint a Supabase-shaped HS256 access token for API tests."""
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    claims = {"sub": subject, "exp": int(time.time()) + expires_in}
    if email:
        claims["email"] = email
    payload = _b64(json.dumps(claims).encode())
    signature = hmac.new(
        secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256
    ).digest()
    return f"{header}.{payload}.{_b64(signature)}"


def user_api_client(
    app,
    subject: str,
    email: str | None = None,
    guest_session: str | None = None,
) -> TestClient:
    """TestClient that is signed in, optionally still carrying a guest trial id."""
    headers = {"Authorization": f"Bearer {make_access_token(subject, email)}"}
    if guest_session:
        headers[GUEST_SESSION_HEADER] = guest_session
    return TestClient(app, headers=headers)
