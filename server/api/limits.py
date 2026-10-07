"""Rate limits and job limits, kept in Redis.

Stage 1 limits for anonymous visitors (Stage 1 plan §10); daily character quotas
and signed-in limits arrive with accounts in M5.
"""

from __future__ import annotations

import time

from server import events
from server.api.auth import Caller
from server.api.errors import APIError
from server.config import Settings

ACTIVE = ("queued", "running")


def _owner_jobs_key(owner: str) -> str:
    return f"owner:{owner}:jobs"


async def check_rate(redis, settings: Settings, ip: str, bucket: str = "jobs") -> None:
    """At most rate_limit_per_minute requests per IP per minute (fixed one-minute windows)."""
    window = int(time.time() // 60)
    key = f"rate:{bucket}:{ip}:{window}"
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, 120)
    count, _ = await pipe.execute()
    if count > settings.rate_limit_per_minute:
        retry = 60 - int(time.time() % 60)
        raise APIError("rate_limited", "Too many requests. Try again in a few seconds.", retry)


async def check_text_length(settings: Settings, text: str) -> None:
    if len(text) > settings.anon_max_chars:
        raise APIError(
            "too_long",
            f"This text is over the limit of {settings.anon_max_chars:,} characters per request.",
        )


async def check_active_jobs(redis, settings: Settings, caller: Caller) -> None:
    """At most max_active_jobs jobs queued or running per caller."""
    key = _owner_jobs_key(caller.owner)
    active = 0
    for job_id in await redis.smembers(key):
        job_id = job_id.decode()
        status = await redis.hget(events.record_key(job_id), "status")
        if status is not None and status.decode() in ACTIVE:
            active += 1
        else:
            await redis.srem(key, job_id)  # finished or expired
    if active >= settings.max_active_jobs:
        raise APIError(
            "rate_limited",
            "You already have a job running. Wait for it to finish or cancel it.",
            retry_after=5,
        )


async def remember_active_job(redis, settings: Settings, caller: Caller, job_id: str) -> None:
    key = _owner_jobs_key(caller.owner)
    await redis.sadd(key, job_id)
    await redis.expire(key, settings.job_record_ttl_seconds)


async def check_queue_space(queue, settings: Settings, queue_name: str) -> None:
    if await queue.queued_count(queue_name) >= settings.max_queued_jobs:
        raise APIError("busy", "The service is busy right now. Try again in a minute.", 60)
