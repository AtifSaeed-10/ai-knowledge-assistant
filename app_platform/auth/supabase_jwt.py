"""
Supabase access-token verification (HS256).

Implemented against the standard library so the deployment needs no extra
dependency. Swap this module to move to another OIDC provider; the rest of
the platform only consumes the returned claims.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from typing import Any

from app_platform import settings


class TokenError(Exception):
    """Token is missing, malformed, expired, or not signed by this project."""


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(segment + padding)
    except (binascii.Error, ValueError) as exc:
        raise TokenError("malformed token segment") from exc


def _decode_json_segment(segment: str) -> dict[str, Any]:
    """Decode one base64url JSON segment. Any garbage becomes a TokenError."""
    raw = _b64url_decode(segment)
    try:
        value = json.loads(raw or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TokenError("malformed token segment") from exc
    if not isinstance(value, dict):
        raise TokenError("malformed token segment")
    return value


def bearer_token(authorization: str | None) -> str | None:
    """Extract the raw token from an Authorization header."""
    value = (authorization or "").strip()
    if not value:
        return None
    parts = value.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


def verify_token(token: str) -> dict[str, Any]:
    """
    Validate signature and expiry; return the claim set.

    Raises TokenError on any failure so callers never see partial claims.
    """
    secret = settings.SUPABASE_JWT_SECRET
    if not secret:
        raise TokenError("auth is not configured")

    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("malformed token")

    header_b64, payload_b64, signature_b64 = parts

    header = _decode_json_segment(header_b64)
    if header.get("alg") != "HS256":
        raise TokenError("unsupported token algorithm")

    expected = hmac.new(
        secret.encode("utf-8"),
        f"{header_b64}.{payload_b64}".encode("ascii"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(expected, _b64url_decode(signature_b64)):
        raise TokenError("token signature mismatch")

    claims = _decode_json_segment(payload_b64)

    expiry = claims.get("exp")
    if isinstance(expiry, (int, float)) and time.time() >= float(expiry):
        raise TokenError("token expired")

    if not claims.get("sub"):
        raise TokenError("token has no subject")

    return claims
