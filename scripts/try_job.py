"""Queue a speech job and follow it live, like the API and browser will.

With the docker compose stack running:

    python scripts/try_job.py "Hello from the worker."
    python scripts/try_job.py --long                  # a few minutes of audio
    python scripts/try_job.py --long --cancel-after 3  # cancel after 3 seconds

Prints the events as they arrive, then downloads the MP3 through its signed URL
and checks that it plays.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import sys
import time
import urllib.request
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import redis.asyncio as aioredis  # noqa: E402
from arq import create_pool  # noqa: E402
from arq.connections import RedisSettings  # noqa: E402

from server import events  # noqa: E402
from server.worker.jobs import JobRequest  # noqa: E402

LONG_TEXT = (
    "The history of speech synthesis goes back centuries, to mechanical devices that "
    "imitated the human vocal tract. In the twentieth century, electronic systems made "
    "it possible to generate intelligible speech from text, although the voices sounded "
    "robotic for decades. Neural networks changed that, and today small open models can "
    "produce natural speech on an ordinary processor.\n\n"
) * 8


@dataclass
class JobResult:
    job_id: str
    final: dict = field(default_factory=dict)
    queued_at: float = 0.0
    started_at: float | None = None
    first_audio_at: float | None = None
    finished_at: float | None = None
    audio_bytes: int = 0
    chunks: int = 0

    @property
    def audio_seconds(self) -> float:
        return self.audio_bytes / 2 / 24_000


async def run(
    redis_url: str,
    request: JobRequest,
    cancel_after: float | None = None,
    verbose: bool = True,
) -> JobResult:
    """Enqueue one job and collect its events until the final one."""
    job_id = "j_" + uuid.uuid4().hex[:16]
    result = JobResult(job_id)
    redis = aioredis.from_url(redis_url)
    pubsub = redis.pubsub()
    await pubsub.subscribe(events.channel(job_id))  # subscribe first so nothing is missed
    await redis.hset(events.record_key(job_id), mapping={"status": "queued"})

    pool = await create_pool(RedisSettings.from_dsn(redis_url))
    result.queued_at = time.perf_counter()
    await pool.enqueue_job("synthesize", job_id, asdict(request), _job_id=job_id)
    if cancel_after is not None:
        asyncio.get_running_loop().call_later(
            cancel_after,
            lambda: asyncio.ensure_future(redis.set(events.cancel_key(job_id), 1, ex=600)),
        )

    def elapsed(t: float) -> str:
        return f"{t - result.queued_at:6.2f}s"

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        now = time.perf_counter()
        kind, body = events.decode(message["data"])
        if kind == "audio":
            result.chunks += 1
            result.audio_bytes += len(body)
            if result.first_audio_at is None:
                result.first_audio_at = now
                if verbose:
                    print(f"{elapsed(now)}  first audio ({len(body) / 48_000:.1f}s of speech)")
            continue
        if body["type"] == "started":
            result.started_at = now
        if verbose:
            print(f"{elapsed(now)}  {body}")
        if body["type"] in events.FINAL_EVENTS:
            result.final, result.finished_at = body, now
            break

    await pubsub.aclose()
    await redis.aclose()
    await pool.aclose()
    return result


def check_download(url: str) -> str:
    import soundfile as sf

    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 (our own signed URL)
        data = resp.read()
        content_type = resp.headers.get("Content-Type")
    clip, sr = sf.read(io.BytesIO(data))
    return f"{len(data) / 1024:.0f} KB {content_type}, plays: {len(clip) / sr:.1f}s at {sr} Hz"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("text", nargs="?", default="Hello from the speech worker. This is a test.")
    parser.add_argument("--long", action="store_true", help="use a long text")
    parser.add_argument("--voice", default="af_heart")
    parser.add_argument("--lang", default="a")
    parser.add_argument("--cancel-after", type=float, help="cancel after N seconds")
    parser.add_argument("--redis", default="redis://localhost:6379/0")
    args = parser.parse_args()

    request = JobRequest(
        text=LONG_TEXT if args.long else args.text, lang=args.lang, voice=args.voice
    )
    result = asyncio.run(run(args.redis, request, args.cancel_after))

    print(f"\nreceived {result.chunks} audio chunk(s), {result.audio_seconds:.1f}s of speech")
    if result.final.get("type") == "done":
        total = result.finished_at - result.queued_at
        print(f"total {total:.1f}s ({result.audio_seconds / total:.1f}x real time)")
        print("download:", check_download(result.final["url"]))
    return 0 if result.final.get("type") in ("done", "cancelled") else 1


if __name__ == "__main__":
    sys.exit(main())
