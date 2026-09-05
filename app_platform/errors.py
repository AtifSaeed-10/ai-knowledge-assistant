"""
Stable API errors for the platform layer.

Clients branch on `code`, never on prose, so copy can change without
breaking the frontend.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

CODE_AUTH_REQUIRED = "AUTH_REQUIRED"
CODE_QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
CODE_FORBIDDEN = "FORBIDDEN"
CODE_PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"

# 402 is used for "trial finished, sign in to continue" so it never reads as
# a permissions bug in client logs.
STATUS_QUOTA_EXCEEDED = 402


def _detail(code: str, message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    if extra:
        payload.update(extra)
    return payload


def auth_required(message: str = "Sign in to continue.") -> HTTPException:
    return HTTPException(status_code=401, detail=_detail(CODE_AUTH_REQUIRED, message))


def quota_exceeded(
    message: str,
    *,
    limit: int,
    used: int,
    resource: str,
    upgrade_hint: str = "sign_in",
) -> HTTPException:
    return HTTPException(
        status_code=STATUS_QUOTA_EXCEEDED,
        detail=_detail(
            CODE_QUOTA_EXCEEDED,
            message,
            {
                "resource": resource,
                "limit": limit,
                "used": used,
                "upgrade_hint": upgrade_hint,
            },
        ),
    )


def forbidden(message: str = "You do not have access to this resource.") -> HTTPException:
    return HTTPException(status_code=403, detail=_detail(CODE_FORBIDDEN, message))


def payload_too_large(message: str, *, limit_mb: int) -> HTTPException:
    return HTTPException(
        status_code=413,
        detail=_detail(CODE_PAYLOAD_TOO_LARGE, message, {"limit_mb": limit_mb}),
    )
