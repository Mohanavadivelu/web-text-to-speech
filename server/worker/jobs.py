"""Runs one speech job: engine → live audio events in Redis → MP3 in storage.

run_job() is synchronous (the engine is CPU-bound) and is called in a thread by the
arq worker. Its dependencies are passed in, so tests can use fakes.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from server import events
from server.config import Settings
from server.engine import audio, text
from server.engine.synth import SAMPLE_RATE, GenerationCancelled
from server.worker.storage import CONTENT_TYPES, audio_key

log = logging.getLogger(__name__)

CANCEL_POLL_SECONDS = 0.1


@dataclass
class JobRequest:
    text: str
    lang: str
    voice: str
    speed: float = 1.0
    pitch: float = 0.0
    blend_voice: str | None = None
    blend_ratio: float = 0.5
    pronunciations: list[dict] = field(default_factory=list)
    owner_kind: str = "anon"  # "users" or "anon"
    owner_id: str = "local"
    wav: bool = False  # also store a WAV copy (signed-in users)
    cache_key: str | None = None  # remember the result so identical requests reuse it


class _Stopper:
    """Turns a cancel request or a timeout into the engine's cancel_event."""

    def __init__(self, redis, job_id: str, timeout_seconds: float):
        self.event = threading.Event()
        self.timed_out = False
        self._redis = redis
        self._job_id = job_id
        self._deadline = time.monotonic() + timeout_seconds
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._watch, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._done.set()
        self._thread.join(timeout=1)

    def _watch(self):
        while not self._done.wait(CANCEL_POLL_SECONDS):
            if time.monotonic() > self._deadline:
                self.timed_out = True
                self.event.set()
                return
            if self._redis.exists(events.cancel_key(self._job_id)):
                self.event.set()
                return


def job_timeout(request: JobRequest, engine, settings: Settings) -> float:
    """max(minimum, 3 × the expected generation time)."""
    audio_seconds = text.estimate_seconds(request.text, request.lang, request.speed)
    expected = engine.estimate_generation_seconds(audio_seconds)
    return max(settings.min_job_timeout_seconds, 3 * expected)


def run_job(
    job_id: str,
    request: JobRequest,
    *,
    engine,
    storage,
    redis,
    settings: Settings,
    on_finish: Callable[..., None] | None = None,
) -> dict:
    """Run a job to completion and return its final event."""
    record = events.record_key(job_id)
    publisher = events.EventPublisher(redis, job_id, settings.job_event_ttl_seconds)
    publisher.reset()  # a retried job starts over
    redis.hset(record, mapping={"status": "running", "progress": 0})
    redis.expire(record, settings.job_record_ttl_seconds)

    estimated = text.estimate_seconds(request.text, request.lang, request.speed)
    publisher.event(type="started", sample_rate=SAMPLE_RATE, estimated_seconds=round(estimated, 1))

    last_percent = -1

    def on_progress(percent: int) -> None:
        nonlocal last_percent
        if percent != last_percent:
            last_percent = percent
            redis.hset(record, "progress", percent)
            publisher.event(type="progress", percent=percent)

    def finish(status: str, *, message=None, key=None, wav_key=None, duration=None) -> dict:
        """Store the final status and publish the matching final event (type == status)."""
        fields = {"status": status}
        final = {"type": status}
        if message:
            fields["error"] = final["message"] = message
        if key:
            fields["key"] = key
        if wav_key:
            fields["wav_key"] = wav_key
        if duration is not None:
            fields["audio_seconds"] = final["duration"] = duration
        redis.hset(record, mapping=fields)
        if on_finish is not None:
            try:  # the Postgres job record (history); speech must not fail because of it
                on_finish(
                    job_id, status, audio_seconds=duration, storage_key=key,
                    wav_key=wav_key, error=message,
                )  # fmt: skip
            except Exception:
                log.exception("Job %s: could not record the result", job_id)
        publisher.event(**final)
        return final

    started = time.perf_counter()
    try:
        with _Stopper(redis, job_id, job_timeout(request, engine, settings)) as stopper:
            result = engine.generate(
                request.text,
                request.lang,
                request.voice,
                speed=request.speed,
                pitch=request.pitch,
                blend_voice=request.blend_voice,
                blend_ratio=request.blend_ratio,
                pronunciations=request.pronunciations,
                first_segment_chars=settings.first_segment_chars,
                on_chunk=lambda chunk: publisher.audio(audio.to_pcm16(chunk)),
                on_progress=on_progress,
                cancel_event=stopper.event,
            )
    except GenerationCancelled:
        if stopper.timed_out:
            log.warning("Job %s timed out", job_id)
            return finish(
                "error", message="This took too long and was stopped. Try a shorter text."
            )
        log.info("Job %s cancelled", job_id)
        return finish("cancelled")
    except ValueError as exc:  # invalid input; the message is meant for the user
        return finish("error", message=str(exc))
    except Exception:
        log.exception("Job %s failed", job_id)
        return finish("error", message="Something went wrong on our side. Please try again.")

    duration = round(len(result) / SAMPLE_RATE, 2)
    key = audio_key(request.owner_kind, request.owner_id, job_id, "mp3")
    wav_key = (
        audio_key(request.owner_kind, request.owner_id, job_id, "wav") if request.wav else None
    )
    try:
        storage.put(key, audio.encode_mp3(result), CONTENT_TYPES["mp3"])
        if wav_key:
            storage.put(wav_key, audio.encode_wav(result), CONTENT_TYPES["wav"])
    except Exception:
        log.exception("Job %s: saving the audio failed", job_id)
        return finish(
            "error", message="The audio was made but couldn't be saved. Please try again."
        )
    log.info(
        "Job %s done: %d chars, %.1fs audio in %.1fs",
        job_id, len(request.text), duration, time.perf_counter() - started,
    )  # fmt: skip
    if request.cache_key:
        redis.set(
            events.cache_entry_key(request.cache_key),
            f"{key}|{duration}",
            ex=settings.cache_ttl_seconds,
        )
    return finish("done", key=key, wav_key=wav_key, duration=duration)
