"""arq worker: loads the speech engine once and runs speech jobs one at a time.

    arq server.worker.main.WorkerSettings

Each worker process runs one job at a time (the engine already uses every CPU
thread it's given); run more worker processes to handle more jobs in parallel.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import socket
from dataclasses import asdict

import redis as redis_sync
from arq.connections import RedisSettings

from server.config import get_settings
from server.engine.synth import KokoroEngine
from server.worker.jobs import JobRequest, run_job
from server.worker.storage import Storage

log = logging.getLogger(__name__)

HEARTBEAT_PREFIX = "workers:heartbeat:"
HEARTBEAT_SECONDS = 10
WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"


async def synthesize(ctx: dict, job_id: str, request: dict) -> dict:
    """arq job: run a speech job in a thread so the event loop stays responsive."""
    job_request = JobRequest(**request)
    return await asyncio.to_thread(
        run_job,
        job_id,
        job_request,
        engine=ctx["engine"],
        storage=ctx["storage"],
        redis=ctx["redis_sync"],
        settings=ctx["settings"],
    )


async def _heartbeat(redis) -> None:
    while True:
        await redis.set(HEARTBEAT_PREFIX + WORKER_ID, "1", ex=HEARTBEAT_SECONDS * 3)
        await asyncio.sleep(HEARTBEAT_SECONDS)


async def startup(ctx: dict) -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    ctx["settings"] = settings
    ctx["redis_sync"] = redis_sync.Redis.from_url(settings.redis_url)
    ctx["storage"] = Storage(settings)
    if settings.r2_endpoint_url:  # development store: create the bucket if needed
        await asyncio.to_thread(ctx["storage"].ensure_bucket)
    engine = KokoroEngine(threads=settings.engine_threads)
    await asyncio.to_thread(engine.load)
    ctx["engine"] = engine
    ctx["heartbeat"] = asyncio.create_task(_heartbeat(ctx["redis"]))
    log.info("Worker %s ready", WORKER_ID)


async def shutdown(ctx: dict) -> None:
    task = ctx.get("heartbeat")
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    if "redis" in ctx:
        await ctx["redis"].delete(HEARTBEAT_PREFIX + WORKER_ID)
    if "redis_sync" in ctx:
        ctx["redis_sync"].close()


class WorkerSettings:
    functions = [synthesize]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 1  # one job per process; the engine is CPU-bound
    max_tries = 2  # retried only if a worker dies mid-job
    job_timeout = 3600  # hard upper bound; run_job applies the real per-job timeout
    keep_result = 3600
    health_check_interval = 30


def job_payload(request: JobRequest) -> dict:
    """The dict that is sent through the queue for a JobRequest."""
    return asdict(request)
