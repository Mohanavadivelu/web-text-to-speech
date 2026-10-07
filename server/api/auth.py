"""Who is calling.

Until accounts arrive (M5), every visitor is anonymous and identified by a random
ID in an HMAC-signed cookie, so it can't be forged or used to reach someone else's
jobs. The client IP is used for rate limits.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

from fastapi import Request, Response
from starlette.requests import HTTPConnection

from server.config import Settings

COOKIE = "anon_id"
COOKIE_MAX_AGE = 365 * 24 * 3600


@dataclass(frozen=True)
class Caller:
    kind: str  # "anon" (accounts add "users" in M5)
    id: str
    ip: str
    new_cookie: str | None = None  # set when the visitor needs a cookie

    @property
    def owner(self) -> str:
        return f"{self.kind}:{self.id}"


def _sign(anon_id: str, secret: str) -> str:
    mac = hmac.new(secret.encode(), anon_id.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{anon_id}.{mac}"


def _verify(cookie: str | None, secret: str) -> str | None:
    if not cookie or "." not in cookie:
        return None
    anon_id = cookie.split(".", 1)[0]
    return anon_id if hmac.compare_digest(_sign(anon_id, secret), cookie) else None


def client_ip(conn: HTTPConnection, settings: Settings) -> str:
    # Behind Cloudflare (M6) the real address is in CF-Connecting-IP. Without Cloudflare
    # in front, anyone could send that header, so it's only trusted when configured.
    if settings.trust_cloudflare_ip_header and conn.headers.get("cf-connecting-ip"):
        return conn.headers["cf-connecting-ip"]
    return conn.client.host if conn.client else "unknown"


def identify(conn: HTTPConnection, settings: Settings, create: bool = True) -> Caller | None:
    """The caller of a request or WebSocket. Without a valid cookie, a new ID is made
    (create=True) or None is returned."""
    secret = settings.anon_cookie_secret
    ip = client_ip(conn, settings)
    anon_id = _verify(conn.cookies.get(COOKIE), secret)
    if anon_id:
        return Caller("anon", anon_id, ip)
    if not create:
        return None
    anon_id = "a" + secrets.token_hex(12)
    return Caller("anon", anon_id, ip, new_cookie=_sign(anon_id, secret))


def set_cookie(response: Response, caller: Caller, secure: bool) -> None:
    if caller.new_cookie:
        response.set_cookie(
            COOKIE,
            caller.new_cookie,
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            secure=secure,
            samesite="lax",
        )


def caller_dependency(request: Request) -> Caller:
    return identify(request, request.app.state.services.settings)
