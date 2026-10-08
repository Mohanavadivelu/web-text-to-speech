"""Services the API uses, created once at startup and shared by all requests.

Tests replace them with fakes through `Services`.
"""

from __future__ import annotations

import asyncio
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from fastapi import Request, WebSocket

from server.config import Settings


class JobQueue(Protocol):
    async def enqueue(self, job_id: str, request: dict, queue: str) -> None: ...

    async def queued_count(self, queue: str) -> int: ...

    async def position(self, queue: str, job_id: str) -> int | None: ...


class ArqJobQueue:
    """Puts jobs on arq queues for the workers."""

    def __init__(self, pool):
        self._pool = pool

    async def enqueue(self, job_id: str, request: dict, queue: str) -> None:
        await self._pool.enqueue_job(
            "synthesize", job_id, request, _job_id=job_id, _queue_name=queue
        )

    async def queued_count(self, queue: str) -> int:
        return await self._pool.zcard(queue)

    async def position(self, queue: str, job_id: str) -> int | None:
        """How many jobs are ahead of this one (None once a worker has taken it)."""
        return await self._pool.zrank(queue, job_id)

    async def close(self) -> None:
        await self._pool.aclose()


class BotCheck(Protocol):
    async def verify(self, token: str | None, ip: str) -> bool: ...


class Turnstile:
    """Cloudflare Turnstile: is this anonymous request from a person? (Stage 1 plan §10)"""

    URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

    def __init__(self, secret: str):
        self._secret = secret

    async def verify(self, token: str | None, ip: str) -> bool:
        if not self._secret:  # development without a key: no check
            return True
        if not token:
            return False
        return await asyncio.to_thread(self._siteverify, token, ip)

    def _siteverify(self, token: str, ip: str) -> bool:
        data = urllib.parse.urlencode(
            {"secret": self._secret, "response": token, "remoteip": ip}
        ).encode()
        try:
            with urllib.request.urlopen(self.URL, data=data, timeout=5) as resp:  # noqa: S310
                return bool(json.load(resp).get("success"))
        except Exception:
            return False


@dataclass
class Services:
    settings: Settings
    redis: object  # redis.asyncio.Redis
    queue: JobQueue
    storage: object  # server.worker.storage.Storage (sync; call it in a thread)
    db: object  # server.db.Database
    verifier: object  # server.api.auth.TokenVerifier
    bots: BotCheck


def services(request: Request) -> Services:
    return request.app.state.services


def ws_services(websocket: WebSocket) -> Services:
    return websocket.app.state.services
