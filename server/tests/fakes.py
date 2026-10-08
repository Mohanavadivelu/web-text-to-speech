"""Fakes for tests that don't need the real model, storage or queue."""

from __future__ import annotations

import time

import numpy as np

from server.engine.synth import GenerationCancelled

CHUNK = np.full(2400, 0.1, dtype=np.float32)  # 0.1 s of audio


class FakeEngine:
    def __init__(self, chunks=3, delay=0.0, error=None, chunk_seconds=0.1):
        self.chunks, self.delay, self.error = chunks, delay, error
        self.chunk = np.full(round(24_000 * chunk_seconds), 0.1, dtype=np.float32)
        self.calls = []

    def estimate_generation_seconds(self, audio_seconds):
        return audio_seconds / 3

    def generate(self, source_text, lang, voice, **kw):
        self.calls.append(kw)
        if self.error:
            raise self.error
        parts = []
        for i in range(self.chunks):
            deadline = time.monotonic() + self.delay
            while time.monotonic() < deadline:
                if kw["cancel_event"].is_set():
                    raise GenerationCancelled()
                time.sleep(0.01)
            kw["on_chunk"](self.chunk)
            kw["on_progress"](int((i + 1) / self.chunks * 100))
            parts.append(self.chunk)
        return np.concatenate(parts)


class FakeStorage:
    def __init__(self, fail=False):
        self.objects, self.fail = {}, fail

    def put(self, key, data, content_type):
        if self.fail:
            raise ConnectionError("storage down")
        self.objects[key] = (data, content_type)

    def copy(self, source_key, dest_key):
        if source_key not in self.objects:
            raise KeyError(source_key)
        self.objects[dest_key] = self.objects[source_key]

    def signed_url(self, key, filename=None):
        return f"https://storage.test/{key}?signature=abc"


class FakeQueue:
    def __init__(self):
        self.jobs: list[tuple[str, dict, str]] = []

    async def enqueue(self, job_id, request, queue):
        self.jobs.append((job_id, request, queue))

    async def queued_count(self, queue):
        return sum(1 for _, _, q in self.jobs if q == queue)

    async def position(self, queue, job_id):
        waiting = [j for j, _, q in self.jobs if q == queue]
        return waiting.index(job_id) if job_id in waiting else None

    async def close(self):
        pass


class FakeDatabase:
    """In-memory stand-in for server.db.PostgresDatabase."""

    def __init__(self):
        self.jobs: dict[str, dict] = {}
        self.pronunciations: dict[str, list[dict]] = {}
        self.usage: dict[tuple, dict] = {}

    async def insert_job(self, job):
        import datetime as dt

        self.jobs[job["id"]] = {"created_at": dt.datetime.now(dt.UTC), "wav_key": None} | job

    def record_result(self, job_id, status, **fields):
        """What the worker calls (server.db.record_result_sync)."""
        self.jobs[job_id].update(status=status, **fields)

    async def history(self, user_id, since):
        rows = [
            j for j in self.jobs.values()
            if j.get("user_id") == user_id and j["status"] == "done" and j["created_at"] >= since
        ]  # fmt: skip
        return sorted(rows, key=lambda j: j["created_at"], reverse=True)

    async def get_pronunciations(self, user_id):
        return list(self.pronunciations.get(user_id, []))

    async def put_pronunciations(self, user_id, entries):
        self.pronunciations[user_id] = list(entries)

    async def add_usage(self, subject, day, chars):
        row = self.usage.setdefault((subject, day), {"chars": 0, "jobs": 0})
        row["chars"] += chars
        row["jobs"] += 1

    async def close(self):
        pass


class FakeVerifier:
    """Accepts tokens of the form "user:<uuid>[:email]"."""

    async def verify(self, token):
        from server.api.errors import APIError

        if not token.startswith("user:"):
            raise APIError("unauthorized", "Your session has expired. Please sign in again.")
        _, sub, *email = token.split(":")
        return {"sub": sub, "email": email[0] if email else None}


class FakeBots:
    def __init__(self, allow=True):
        self.allow = allow
        self.tokens = []

    async def verify(self, token, ip):
        self.tokens.append(token)
        return self.allow and token == "human"
