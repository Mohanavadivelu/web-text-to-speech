"""Limits per tier (Stage 1 plan §10), enforced with Redis counters.

anonymous:  2,000 chars per request, 10,000 per day, 2 active jobs, 10 requests/min
signed in: 20,000 chars per request, 100,000 per day, 3 active jobs, 30 requests/min
"""

from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass

from server import events
from server.api.auth import Caller
from server.api.errors import APIError
from server.config import Settings

ACTIVE = ("queued", "running")


@dataclass(frozen=True)
class Limits:
    max_chars: int
    daily_chars: int
    max_active_jobs: int
    per_minute: int
    uploads: bool
    wav: bool


def limits_for(caller: Caller, settings: Settings) -> Limits:
    if caller.signed_in:
        return Limits(
            max_chars=settings.user_max_chars,
            daily_chars=settings.user_daily_chars,
            max_active_jobs=settings.user_max_active_jobs,
            per_minute=settings.user_rate_limit_per_minute,
            uploads=True,
            wav=True,
        )
    return Limits(
        max_chars=settings.anon_max_chars,
        daily_chars=settings.anon_daily_chars,
        max_active_jobs=settings.max_active_jobs,
        per_minute=settings.rate_limit_per_minute,
        uploads=False,
        wav=False,
    )


def today() -> dt.date:
    return dt.datetime.now(dt.UTC).date()


def _owner_jobs_key(owner: str) -> str:
    return f"owner:{owner}:jobs"


def _usage_key(owner: str, day: dt.date) -> str:
    return f"usage:{owner}:{day:%Y%m%d}"


async def check_rate(redis, caller: Caller, limits: Limits, bucket: str = "jobs") -> None:
    """At most `per_minute` requests per minute: per account when signed in, else per IP."""
    window = int(time.time() // 60)
    who = caller.owner if caller.signed_in else caller.ip
    key = f"rate:{bucket}:{who}:{window}"
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, 120)
    count, _ = await pipe.execute()
    if count > limits.per_minute:
        retry = 60 - int(time.time() % 60)
        raise APIError("rate_limited", "Too many requests. Try again in a few seconds.", retry)


def check_text_length(limits: Limits, text: str, caller: Caller) -> None:
    if len(text) > limits.max_chars:
        hint = "" if caller.signed_in else " Sign in for up to 20,000."
        raise APIError(
            "too_long",
            f"This text is over the limit of {limits.max_chars:,} characters per request.{hint}",
        )


async def chars_used_today(redis, caller: Caller) -> int:
    value = await redis.get(_usage_key(caller.owner, today()))
    return int(value or 0)


async def check_daily_quota(redis, caller: Caller, limits: Limits, chars: int) -> None:
    used = await chars_used_today(redis, caller)
    if used + chars > limits.daily_chars:
        left = max(0, limits.daily_chars - used)
        hint = " Sign in for more." if not caller.signed_in else ""
        raise APIError(
            "quota_exceeded",
            f"That's more than today's remaining {left:,} characters "
            f"(limit {limits.daily_chars:,} a day, reset at midnight UTC).{hint}",
        )


async def count_usage(redis, caller: Caller, chars: int) -> None:
    key = _usage_key(caller.owner, today())
    pipe = redis.pipeline()
    pipe.incrby(key, chars)
    pipe.expire(key, 48 * 3600)
    await pipe.execute()


async def check_active_jobs(redis, caller: Caller, limits: Limits) -> None:
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
    if active >= limits.max_active_jobs:
        raise APIError(
            "rate_limited",
            "You already have jobs running. Wait for one to finish or cancel it.",
            retry_after=5,
        )


async def remember_active_job(redis, settings: Settings, caller: Caller, job_id: str) -> None:
    key = _owner_jobs_key(caller.owner)
    await redis.sadd(key, job_id)
    await redis.expire(key, settings.job_record_ttl_seconds)


async def check_queue_space(queue, settings: Settings, queue_name: str) -> None:
    if await queue.queued_count(queue_name) >= settings.max_queued_jobs:
        raise APIError("busy", "The service is busy right now. Try again in a minute.", 60)
