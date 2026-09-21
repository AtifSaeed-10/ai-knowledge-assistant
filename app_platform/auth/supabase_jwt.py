"""
Supabase access-token verification.

Legacy projects still mint HS256 tokens with the shared JWT secret.
Current projects (including this one) mint ES256 tokens; those are
checked against the project's public JWKS. The rest of the platform
only consumes the returned claims.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from typing import Any

from app_platform import settings


class TokenError(Exception):
    """Token is missing, malformed, expired, or not signed by this project."""


_JWKS_TTL_SECONDS = 300
_jwks_cached_at = 0.0
_jwks_keys: list[dict[str, Any]] = []


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


def _b64url_to_int(segment: str) -> int:
    return int.from_bytes(_b64url_decode(segment), "big")


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


def clear_jwks_cache() -> None:
    """Test helper so each case can install its own public keys."""
    global _jwks_cached_at, _jwks_keys
    _jwks_cached_at = 0.0
    _jwks_keys = []


def fetch_jwks() -> list[dict[str, Any]]:
    """Return the project's public signing keys, cached briefly."""
    global _jwks_cached_at, _jwks_keys

    now = time.time()
    if _jwks_keys and now - _jwks_cached_at < _JWKS_TTL_SECONDS:
        return _jwks_keys

    base = (settings.SUPABASE_URL or "").rstrip("/")
    if not base:
        raise TokenError("auth is not configured")

    url = f"{base}/auth/v1/.well-known/jwks.json"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "docusage-api"},
    )
    try:
        import ssl

        import certifi

        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(request, timeout=8, context=context) as response:
            body = json.loads(response.read().decode("utf-8") or "{}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        raise TokenError("could not load signing keys") from exc

    keys = body.get("keys") if isinstance(body, dict) else None
    if not isinstance(keys, list):
        raise TokenError("could not load signing keys")

    _jwks_keys = [key for key in keys if isinstance(key, dict)]
    _jwks_cached_at = now
    return _jwks_keys


def _verify_hs256(header_b64: str, payload_b64: str, signature_b64: str) -> None:
    secret = settings.SUPABASE_JWT_SECRET
    if not secret:
        raise TokenError("auth is not configured")

    expected = hmac.new(
        secret.encode("utf-8"),
        f"{header_b64}.{payload_b64}".encode("ascii"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(expected, _b64url_decode(signature_b64)):
        raise TokenError("token signature mismatch")


def _verify_es256(
    header: dict[str, Any],
    header_b64: str,
    payload_b64: str,
    signature_b64: str,
) -> None:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ec import ECDSA, SECP256R1
        from cryptography.hazmat.primitives.asymmetric.ec import (
            EllipticCurvePublicNumbers,
        )
        from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
        from cryptography.hazmat.primitives.hashes import SHA256
    except ImportError as exc:
        raise TokenError("ES256 verification is not available") from exc

    keys = fetch_jwks()
    kid = header.get("kid")
    candidates = [
        key
        for key in keys
        if key.get("kty") == "EC"
        and key.get("crv") == "P-256"
        and key.get("x")
        and key.get("y")
        and (not kid or key.get("kid") == kid)
    ]
    if not candidates:
        raise TokenError("no matching signing key")

    signature = _b64url_decode(signature_b64)
    if len(signature) != 64:
        raise TokenError("token signature mismatch")
    der = encode_dss_signature(
        int.from_bytes(signature[:32], "big"),
        int.from_bytes(signature[32:], "big"),
    )
    message = f"{header_b64}.{payload_b64}".encode("ascii")

    for key in candidates:
        try:
            public = EllipticCurvePublicNumbers(
                _b64url_to_int(str(key["x"])),
                _b64url_to_int(str(key["y"])),
                SECP256R1(),
            ).public_key()
            public.verify(der, message, ECDSA(SHA256()))
            return
        except (InvalidSignature, ValueError, TokenError):
            continue

    raise TokenError("token signature mismatch")


def _validated_claims(payload_b64: str) -> dict[str, Any]:
    claims = _decode_json_segment(payload_b64)

    expiry = claims.get("exp")
    if isinstance(expiry, (int, float)) and time.time() >= float(expiry):
        raise TokenError("token expired")

    if not claims.get("sub"):
        raise TokenError("token has no subject")

    return claims


def token_email(claims: dict[str, Any]) -> str | None:
    """Google/Supabase may put the address on the token or in metadata."""
    email = claims.get("email")
    if isinstance(email, str) and "@" in email.strip():
        return email.strip()
    for key in ("user_metadata", "app_metadata"):
        meta = claims.get(key)
        if not isinstance(meta, dict):
            continue
        nested = meta.get("email")
        if isinstance(nested, str) and "@" in nested.strip():
            return nested.strip()
    return None


def verify_token(token: str) -> dict[str, Any]:
    """
    Validate signature and expiry; return the claim set.

    Raises TokenError on any failure so callers never see partial claims.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("malformed token")

    header_b64, payload_b64, signature_b64 = parts
    header = _decode_json_segment(header_b64)
    algorithm = header.get("alg")

    if algorithm == "HS256":
        _verify_hs256(header_b64, payload_b64, signature_b64)
    elif algorithm == "ES256":
        _verify_es256(header, header_b64, payload_b64, signature_b64)
    else:
        raise TokenError("unsupported token algorithm")

    return _validated_claims(payload_b64)
