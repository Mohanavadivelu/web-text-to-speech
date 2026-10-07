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

    def signed_url(self, key):
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
