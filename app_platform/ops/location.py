"""
Last-seen country/city for the operator dashboard.

Only CDN/proxy headers are used. The value never leaves /admin/overview.
"""

from __future__ import annotations

from urllib.parse import unquote

from fastapi import Request

from app_platform.auth.context import RequestContext

_UNKNOWN = {"", "xx", "t1", "a1", "a2", "zz"}


def _header(request: Request, *names: str) -> str | None:
    for name in names:
        raw = request.headers.get(name)
        if raw and str(raw).strip():
            return unquote(str(raw).strip().replace("+", " "))
    return None


def location_from_request(request: Request) -> tuple[str | None, str | None]:
    country = _header(
        request,
        "cf-ipcountry",
        "cf-ip-country",
        "x-vercel-ip-country",
        "cloudfront-viewer-country",
        "x-country-code",
    )
    if country:
        country = country.upper()
        if country.lower() in _UNKNOWN or len(country) > 8:
            country = None
    city = _header(
        request,
        "cf-ipcity",
        "x-vercel-ip-city",
        "x-city",
    )
    region = _header(
        request,
        "cf-region",
        "x-vercel-ip-country-region",
        "x-region",
    )
    place = city or region
    if place and len(place) > 80:
        place = place[:80]
    return country, place


def apply_request_location(context: RequestContext, request: Request) -> None:
    country, region = location_from_request(request)
    if not country and not region:
        return
    if context.is_user:
        from database.user_store import update_user_location

        update_user_location(context.actor_id, country, region)
        return
    if context.is_guest:
        from database.guest_store import update_guest_location

        update_guest_location(context.actor_id, country, region)
