"""Speech jobs: create, check, cancel, and stream live over a WebSocket."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import secrets
import time
from dataclasses import asdict

from fastapi import APIRouter, Depends, Response, WebSocket, WebSocketDisconnect

from server import events
from server.api import limits
from server.api.auth import WS_PROTOCOL, Caller, caller_dependency, identify, set_cookie
from server.api.deps import Services, services, ws_services
from server.api.errors import APIError
from server.api.schemas import ErrorResponse, JobCreate, JobOut
from server.engine import model_store, text
from server.worker.jobs import JobRequest
from server.worker.storage import audio_key

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/tts", tags=["tts"])

ERRORS = {
    code: {"model": ErrorResponse} for code in (401, 404, 413, 422, 429, 503)
}  # documented in OpenAPI
WS_NOT_FOUND = 4404
WS_UNAUTHORIZED = 4401
AUDIO_FRAME_BYTES = 48_000  # 1 s of 24 kHz 16-bit mono per WebSocket message


def new_job_id() -> str:
    return "j_" + secrets.token_hex(8)


def cache_key(body: JobCreate, pronunciations: list[dict]) -> str:
    """Same text and settings (and pronunciations) with the same model → same audio."""
    payload = body.model_dump(mode="json", exclude={"turnstile_token", "pronunciations"}) | {
        "pronunciations": pronunciations,
        "model": model_store.REVISION,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


async def _download_url(svc: Services, job_id: str, key: str) -> str:
    """Signed link that plays in the browser and saves as a named file when downloaded."""
    extension = key.rsplit(".", 1)[-1]
    return await asyncio.to_thread(svc.storage.signed_url, key, f"narravo-{job_id}.{extension}")


async def _best_effort(what: str, coroutine) -> None:
    """Job records and usage statistics shouldn't stop speech if the database is down."""
    try:
        await coroutine
    except Exception:
        log.exception("Could not save %s", what)


def _job_row(job_id: str, caller: Caller, body: JobCreate, **extra) -> dict:
    """The Postgres row for a job: settings and lengths, never the text."""
    return {
        "id": job_id,
        "user_id": caller.id if caller.signed_in else None,
        "anon_id": None if caller.signed_in else caller.id,
        "lang": body.lang,
        "voice": body.voice,
        "blend_voice": body.blend_voice,
        "blend_ratio": body.blend_ratio if body.blend_voice else None,
        "speed": body.speed,
        "pitch": body.pitch,
        "chars": len(body.text),
    } | extra


async def _record(svc: Services, job_id: str, caller: Caller) -> dict[str, str]:
    """The job's record, or 404 if it doesn't exist or belongs to someone else."""
    raw = await svc.redis.hgetall(events.record_key(job_id))
    record = {k.decode(): v.decode() for k, v in raw.items()}
    if not record or record.get("owner") != caller.owner:
        raise APIError("not_found", "This job doesn't exist or has expired.")
    return record


async def _job_out(svc: Services, job_id: str, record: dict[str, str]) -> JobOut:
    out = JobOut(
        id=job_id,
        status=record["status"],
        progress=int(record.get("progress", 0)),
        estimated_seconds=float(record["estimated_seconds"])
        if "estimated_seconds" in record
        else None,
        audio_seconds=float(record["audio_seconds"]) if "audio_seconds" in record else None,
        error=record.get("error"),
        stream_url=f"/v1/tts/jobs/{job_id}/stream",
    )
    if out.status == "queued":
        out.queue_position = await svc.queue.position(record["queue"], job_id)
    if out.status == "done" and "key" in record:
        out.url = await _download_url(svc, job_id, record["key"])
        if record.get("wav_key"):
            out.wav_url = await _download_url(svc, job_id, record["wav_key"])
    return out


async def _reuse_cached(svc: Services, body: JobCreate, caller: Caller, job_id: str, key: str):
    """If identical audio was made recently, copy it for this caller. Returns the record or None."""
    entry = await svc.redis.get(events.cache_entry_key(key))
    if entry is None:
        return None
    source_key, duration = entry.decode().rsplit("|", 1)
    dest_key = audio_key(caller.kind, caller.id, job_id)
    try:
        await asyncio.to_thread(svc.storage.copy, source_key, dest_key)
    except Exception:  # expired or missing: just generate it again
        await svc.redis.delete(events.cache_entry_key(key))
        return None
    estimated = round(text.estimate_seconds(body.text, body.lang, body.speed), 1)
    record = {
        "status": "done",
        "owner": caller.owner,
        "queue": "cache",
        "progress": 100,
        "key": dest_key,
        "audio_seconds": duration,
        "estimated_seconds": estimated,
        "chars": len(body.text),
        "created_at": int(time.time()),
    }
    log = events.log_key(job_id)
    pipe = svc.redis.pipeline()
    pipe.hset(events.record_key(job_id), mapping=record)
    pipe.expire(events.record_key(job_id), svc.settings.job_record_ttl_seconds)
    pipe.rpush(
        log,
        events.encode_event(
            {"type": "started", "sample_rate": 24000, "estimated_seconds": estimated}
        ),
        events.encode_event({"type": "done", "duration": float(duration)}),
    )
    pipe.expire(log, svc.settings.job_event_ttl_seconds)
    await pipe.execute()
    return {k: str(v) for k, v in record.items()}


@router.post("/jobs", status_code=201, response_model=JobOut, responses=ERRORS)
async def create_job(
    body: JobCreate,
    response: Response,
    caller: Caller = Depends(caller_dependency),
    svc: Services = Depends(services),
) -> JobOut:
    """Queue text for speech. Follow it live on `stream_url`, or poll the job.

    Anonymous visitors must include a Cloudflare Turnstile token. Signed-in users'
    saved pronunciations are applied unless the request brings its own.
    """
    settings = svc.settings
    lim = limits.limits_for(caller, settings)
    await limits.check_rate(svc.redis, caller, lim)
    if not caller.signed_in and not await svc.bots.verify(body.turnstile_token, caller.ip):
        raise APIError("unauthorized", "Please confirm you're not a robot, then try again.")
    limits.check_text_length(lim, body.text, caller)
    await limits.check_active_jobs(svc.redis, caller, lim)
    set_cookie(response, caller, secure=settings.app_env == "production")

    pronunciations = [p.model_dump() for p in body.pronunciations]
    if caller.signed_in and not pronunciations:
        pronunciations = await svc.db.get_pronunciations(caller.id)

    job_id = new_job_id()
    key = cache_key(body, pronunciations)
    # Signed-in users also get a WAV, which the cache doesn't keep: they always generate
    cached = None if lim.wav else await _reuse_cached(svc, body, caller, job_id, key)
    if cached:
        row = _job_row(
            job_id, caller, body, status="done", cached=True, storage_key=cached["key"],
            audio_seconds=float(cached["audio_seconds"]),
        )  # fmt: skip
        await _best_effort("job", svc.db.insert_job(row))
        return await _job_out(svc, job_id, cached)

    await limits.check_daily_quota(svc.redis, caller, lim, len(body.text))
    queue = (
        settings.queue_short if len(body.text) <= settings.short_job_chars else settings.queue_long
    )
    await limits.check_queue_space(svc.queue, settings, queue)
    estimated = round(text.estimate_seconds(body.text, body.lang, body.speed), 1)
    record = {
        "status": "queued",
        "owner": caller.owner,
        "queue": queue,
        "progress": 0,
        "estimated_seconds": estimated,
        "chars": len(body.text),
        "created_at": int(time.time()),
    }
    await svc.redis.hset(events.record_key(job_id), mapping=record)
    await svc.redis.expire(events.record_key(job_id), settings.job_record_ttl_seconds)
    request = JobRequest(
        text=body.text,
        lang=body.lang,
        voice=body.voice,
        speed=body.speed,
        pitch=body.pitch,
        blend_voice=body.blend_voice,
        blend_ratio=body.blend_ratio,
        pronunciations=pronunciations,
        owner_kind=caller.kind,
        owner_id=caller.id,
        wav=lim.wav,
        cache_key=None if lim.wav else key,
    )
    await _best_effort("job", svc.db.insert_job(_job_row(job_id, caller, body, status="queued")))
    await svc.queue.enqueue(job_id, asdict(request), queue)
    await limits.remember_active_job(svc.redis, settings, caller, job_id)
    await limits.count_usage(svc.redis, caller, len(body.text))
    await _best_effort("usage", svc.db.add_usage(caller.owner, limits.today(), len(body.text)))
    return await _job_out(svc, job_id, {k: str(v) for k, v in record.items()})


@router.get("/jobs/{job_id}", response_model=JobOut, responses=ERRORS)
async def get_job(
    job_id: str, caller: Caller = Depends(caller_dependency), svc: Services = Depends(services)
) -> JobOut:
    """Status, progress and (when done) a fresh download link."""
    return await _job_out(svc, job_id, await _record(svc, job_id, caller))


@router.delete("/jobs/{job_id}", status_code=202, response_model=JobOut, responses=ERRORS)
async def cancel_job(
    job_id: str, caller: Caller = Depends(caller_dependency), svc: Services = Depends(services)
) -> JobOut:
    """Ask the worker to stop. The final status arrives as a `cancelled` event."""
    record = await _record(svc, job_id, caller)
    if record["status"] in limits.ACTIVE:
        await svc.redis.set(events.cancel_key(job_id), 1, ex=svc.settings.job_record_ttl_seconds)
    return await _job_out(svc, job_id, record)


@router.websocket("/jobs/{job_id}/stream")
async def stream_job(websocket: WebSocket, job_id: str) -> None:
    """Live events: JSON text messages for status, binary messages for audio.

    Audio is 16-bit little-endian PCM, mono, at the `sample_rate` given in `started`,
    in frames of up to one second.
    Connecting late (or again) replays everything from the start.
    """
    svc = ws_services(websocket)
    try:
        caller = await identify(websocket, svc.settings, svc.verifier, create=False)
        if caller is None:
            raise APIError("not_found", "")
        await _record(svc, job_id, caller)
    except APIError as exc:
        code = WS_UNAUTHORIZED if exc.code == "unauthorized" else WS_NOT_FOUND
        await websocket.close(code=code)
        return

    # Browsers that send their token as a subprotocol expect one subprotocol back
    offered = websocket.scope.get("subprotocols", [])
    await websocket.accept(subprotocol=WS_PROTOCOL if WS_PROTOCOL in offered else None)
    try:
        async for kind, body in events.follow(svc.redis, job_id):
            if kind == "audio":
                # A segment can be ~30 s of audio; small frames play smoothly and stay
                # well under WebSocket message size limits
                for start in range(0, len(body), AUDIO_FRAME_BYTES):
                    await websocket.send_bytes(body[start : start + AUDIO_FRAME_BYTES])
                continue
            if body["type"] == "done":
                record = await _record(svc, job_id, caller)
                body = body | {"url": await _download_url(svc, job_id, record["key"])}
                if record.get("wav_key"):
                    body["wav_url"] = await _download_url(svc, job_id, record["wav_key"])
            await websocket.send_json(body)
        await websocket.close()
    except WebSocketDisconnect:
        pass
