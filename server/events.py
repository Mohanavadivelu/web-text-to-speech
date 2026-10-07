"""How a job's live events travel through Redis, shared by the worker and the API.

For each job:

    job:<id>           hash: status, progress, audio_seconds, key, error (the job record)
    job:<id>:events    pub/sub channel: live events while the job runs
    job:<id>:replay    list: every event so far, so a late or reconnecting client misses nothing
    job:<id>:cancel    set by the API to cancel the job

Each event is one Redis message: b"J" + JSON for status events, b"A" + PCM16
(24 kHz mono, little-endian) for audio. Status events:

    {"type": "started", "sample_rate": 24000, "estimated_seconds": 12.3}
    {"type": "progress", "percent": 40}
    {"type": "done", "url": "...", "duration": 41.3}
    {"type": "error", "message": "..."}
    {"type": "cancelled"}

If a worker crashes and the job is retried, the replay list is cleared and a
new "started" event is sent: clients drop any audio they had and start over.
"""

from __future__ import annotations

import json
from typing import Literal

JOB_STATUSES = ("queued", "running", "done", "error", "cancelled")
FINAL_EVENTS = ("done", "error", "cancelled")

_JSON, _AUDIO = b"J", b"A"


def record_key(job_id: str) -> str:
    return f"job:{job_id}"


def channel(job_id: str) -> str:
    return f"job:{job_id}:events"


def replay_key(job_id: str) -> str:
    return f"job:{job_id}:replay"


def cancel_key(job_id: str) -> str:
    return f"job:{job_id}:cancel"


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
    """Publishes a job's events and keeps them replayable (synchronous Redis client)."""

    def __init__(self, redis, job_id: str, ttl_seconds: int):
        self._redis = redis
        self._job_id = job_id
        self._ttl = ttl_seconds

    def reset(self) -> None:
        self._redis.delete(replay_key(self._job_id))

    def publish(self, message: bytes) -> None:
        pipe = self._redis.pipeline()
        pipe.rpush(replay_key(self._job_id), message)
        pipe.expire(replay_key(self._job_id), self._ttl)
        pipe.publish(channel(self._job_id), message)
        pipe.execute()

    def event(self, **event) -> None:
        self.publish(encode_event(event))

    def audio(self, pcm16: bytes) -> None:
        self.publish(encode_audio(pcm16))
