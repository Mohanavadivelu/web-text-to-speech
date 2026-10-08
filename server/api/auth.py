"""Who is calling.

Signed-in users send their Supabase access token: in the Authorization header for
HTTP, or as a WebSocket subprotocol ("auth.<token>"), because browsers can't set
headers on WebSockets and tokens must never go in URLs (they'd end up in logs).
Tokens are verified against Supabase's public signing keys (JWKS).

Everyone else is anonymous and identified by a random ID in an HMAC-signed cookie,
so it can't be forged or used to reach someone else's jobs. The client IP is used
for rate limits.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
from dataclasses import dataclass

from fastapi import Request, Response
from starlette.requests import HTTPConnection

from server.api.errors import APIError
from server.config import Settings

COOKIE = "anon_id"
COOKIE_MAX_AGE = 365 * 24 * 3600
WS_PROTOCOL = "kokoro"  # the subprotocol the server answers with
WS_TOKEN_PREFIX = "auth."  # noqa: S105 (a prefix, not a secret)


@dataclass(frozen=True)
class Caller:
    kind: str  # "users" or "anon"
    id: str
    ip: str
    email: str | None = None
    new_cookie: str | None = None  # set when an anonymous visitor needs a cookie

    @property
    def owner(self) -> str:
        return f"{self.kind}:{self.id}"

    @property
    def signed_in(self) -> bool:
        return self.kind == "users"


class TokenVerifier:
    """Checks Supabase access tokens: signature (JWKS), expiry, audience and issuer."""

    def __init__(self, settings: Settings):
        import jwt

        self._jwt = jwt
        self._issuer = settings.jwt_issuer
        self._jwks = jwt.PyJWKClient(
            f"{settings.supabase_url}/auth/v1/.well-known/jwks.json",
            cache_keys=True,
            lifespan=600,
            timeout=5,
        )

    def _verify(self, token: str) -> dict:
        key = self._jwks.get_signing_key_from_jwt(token)
        return self._jwt.decode(
            token,
            key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
            issuer=self._issuer,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )

    async def verify(self, token: str) -> dict:
        """The token's claims; raises APIError("unauthorized") if it isn't valid."""
        try:
            return await asyncio.to_thread(self._verify, token)
        except Exception:
            raise APIError(
                "unauthorized", "Your session has expired. Please sign in again."
            ) from None


def _sign(anon_id: str, secret: str) -> str:
    mac = hmac.new(secret.encode(), anon_id.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{anon_id}.{mac}"


def _verify_cookie(cookie: str | None, secret: str) -> str | None:
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


def bearer_token(conn: HTTPConnection) -> str | None:
    header = conn.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    for protocol in conn.scope.get("subprotocols", []):  # WebSocket
        if protocol.startswith(WS_TOKEN_PREFIX):
            return protocol[len(WS_TOKEN_PREFIX) :] or None
    return None


async def identify(
    conn: HTTPConnection, settings: Settings, verifier, create: bool = True
) -> Caller | None:
    """The caller of a request or WebSocket.

    A token makes a signed-in caller (an invalid token is an error, not anonymous).
    Otherwise the anon cookie is used; without one, a new ID is made (create=True)
    or None is returned.
    """
    ip = client_ip(conn, settings)
    token = bearer_token(conn)
    if token:
        claims = await verifier.verify(token)
        return Caller("users", claims["sub"], ip, email=claims.get("email"))

    secret = settings.anon_cookie_secret
    anon_id = _verify_cookie(conn.cookies.get(COOKIE), secret)
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


async def caller_dependency(request: Request) -> Caller:
    svc = request.app.state.services
    return await identify(request, svc.settings, svc.verifier)


async def user_dependency(request: Request) -> Caller:
    """Like caller_dependency, but only for signed-in users."""
    caller = await caller_dependency(request)
    if not caller.signed_in:
        raise APIError("unauthorized", "Sign in to use this.")
    return caller
