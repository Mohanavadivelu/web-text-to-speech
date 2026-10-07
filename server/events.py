"""How a job's live events travel through Redis, shared by the worker and the API.

For each job:

    job:<id>           hash: the job record (status, owner, progress, key, ...)
    job:<id>:log       list: every event so far, in order (expires after a while)
    job:<id>:notify    pub/sub channel: "the log has grown" signals, no data
    job:<id>:cancel    set by the API to cancel the job

Listeners subscribe to the channel, then read the log from where they left off
each time a signal arrives. A browser that connects late or reconnects therefore
gets every event exactly once, in order, with no gaps.

Each log entry is b"J" + JSON for status events, or b"A" + PCM16 audio (24 kHz
mono, little-endian). Status events:

    {"type": "started", "sample_rate": 24000, "estimated_seconds": 12.3}
    {"type": "progress", "percent": 40}
    {"type": "done", "duration": 41.3}            (the API adds a signed "url")
    {"type": "error", "message": "..."}
    {"type": "cancelled"}

If a worker crashes and the job is retried, the log is cleared and a new
"started" event is sent: clients drop any audio they had and start over.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Literal

JOB_STATUSES = ("queued", "running", "done", "error", "cancelled")
WORKER_HEARTBEAT_PREFIX = "workers:heartbeat:"  # one key per live worker, with a short expiry
FINAL_EVENTS = ("done", "error", "cancelled")

_JSON, _AUDIO = b"J", b"A"


def record_key(job_id: str) -> str:
    return f"job:{job_id}"


def log_key(job_id: str) -> str:
    return f"job:{job_id}:log"


def notify_channel(job_id: str) -> str:
    return f"job:{job_id}:notify"


def cancel_key(job_id: str) -> str:
    return f"job:{job_id}:cancel"


def cache_entry_key(cache_key: str) -> str:
    """Points to a finished result ("<storage key>|<duration>") for identical requests."""
    return f"cache:{cache_key}"


def encode_event(event: dict) -> bytes:
    return _JSON + json.dumps(event, separators=(",", ":")).encode()


def encode_audio(pcm16: bytes) -> bytes:
    return _AUDIO + pcm16


def decode(message: bytes) -> tuple[Literal["event"], dict] | tuple[Literal["audio"], bytes]:
    kind, body = message[:1], message[1:]
    if kind == _JSON:
        return "event", json.loads(body)
    if kind == _AUDIO:
        return "audio", body
    raise ValueError("Unknown event type.")


class EventPublisher:
    """Appends a job's events to its log and signals listeners (synchronous Redis client)."""

    def __init__(self, redis, job_id: str, ttl_seconds: int):
        self._redis = redis
        self._job_id = job_id
        self._ttl = ttl_seconds

    def reset(self) -> None:
        self._redis.delete(log_key(self._job_id))

    def publish(self, message: bytes) -> None:
        pipe = self._redis.pipeline()
        pipe.rpush(log_key(self._job_id), message)
        pipe.expire(log_key(self._job_id), self._ttl)
        pipe.publish(notify_channel(self._job_id), b"")
        pipe.execute()

    def event(self, **event) -> None:
        self.publish(encode_event(event))

    def audio(self, pcm16: bytes) -> None:
        self.publish(encode_audio(pcm16))


async def follow(
    redis, job_id: str, poll_seconds: float = 1.0
) -> AsyncIterator[tuple[str, object]]:
    """Yield a job's decoded events from the start until its final event (async Redis client).

    A "started" event after other events means the job was retried: the caller
    should discard what it has. Polls every poll_seconds as a safety net in case
    a signal is missed.
    """
    pubsub = redis.pubsub()
    await pubsub.subscribe(notify_channel(job_id))
    seen = 0
    try:
        while True:
            if await redis.llen(log_key(job_id)) < seen:
                seen = 0  # the log was cleared: the job is being retried from the start
            entries = await redis.lrange(log_key(job_id), seen, -1)
            for entry in entries:
                seen += 1
                kind, body = decode(entry)
                yield kind, body
                if kind == "event" and body["type"] in FINAL_EVENTS:
                    return
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(_next_signal(pubsub), timeout=poll_seconds)
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()


async def _next_signal(pubsub) -> None:
    while True:
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=None)
        if message is not None:
            return
