"""Create a speech job through the API and follow it live, like the browser will.

With the docker compose stack running:

    python scripts/try_job.py "Hello from the API."
    python scripts/try_job.py --long                   # a few minutes of audio
    python scripts/try_job.py --long --cancel-after 3  # cancel after 3 seconds

POSTs the job, streams its events and audio over the WebSocket, then downloads
the MP3 through its signed link and checks that it plays.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from websockets.asyncio.client import connect

LONG_TEXT = (
    "The history of speech synthesis goes back centuries, to mechanical devices that "
    "imitated the human vocal tract. In the twentieth century, electronic systems made "
    "it possible to generate intelligible speech from text, although the voices sounded "
    "robotic for decades. Neural networks changed that, and today small open models can "
    "produce natural speech on an ordinary processor.\n\n"
) * 4


@dataclass
class JobResult:
    job_id: str = ""
    status_code: int = 0
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


def _request(method: str, url: str, body: dict | None = None, cookie: str = ""):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)  # noqa: S310 (local API)
    req.add_header("Content-Type", "application/json")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            set_cookie = resp.headers.get("Set-Cookie", "")
            return resp.status, json.loads(resp.read()), set_cookie.split(";", 1)[0]
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read()), ""


async def run(
    api: str, body: dict, cancel_after: float | None = None, verbose: bool = True
) -> JobResult:
    """Create one job and collect its stream until the final event."""
    result = JobResult(queued_at=time.perf_counter())
    # Anonymous jobs need a Turnstile token; the development stack uses Cloudflare's test
    # secret, which accepts this dummy token (a real deployment needs a real one)
    body = {"turnstile_token": "XXXX.DUMMY.TOKEN.XXXX"} | body
    status, job, cookie = await asyncio.to_thread(_request, "POST", f"{api}/v1/tts/jobs", body)
    result.status_code = status
    if status != 201:
        result.final = job
        if verbose:
            print(f"HTTP {status}: {job}")
        return result
    result.job_id = job["id"]
    if verbose:
        position = job["queue_position"]
        print(f"  0.00s  created {job['id']} ({job['status']}, queue position {position})")

    def elapsed(t: float) -> str:
        return f"{t - result.queued_at:6.2f}s"

    if cancel_after is not None:

        async def cancel():
            await asyncio.sleep(cancel_after)
            await asyncio.to_thread(
                _request, "DELETE", f"{api}/v1/tts/jobs/{job['id']}", None, cookie
            )

        asyncio.get_running_loop().create_task(cancel())

    ws_url = api.replace("http", "ws", 1) + job["stream_url"]
    async with connect(ws_url, additional_headers={"Cookie": cookie}) as ws:
        async for message in ws:
            now = time.perf_counter()
            if isinstance(message, bytes):
                result.chunks += 1
                result.audio_bytes += len(message)
                if result.first_audio_at is None:
                    result.first_audio_at = now
                    if verbose:
                        print(
                            f"{elapsed(now)}  first audio ({len(message) / 48_000:.1f}s of speech)"
                        )
                continue
            event = json.loads(message)
            if event["type"] == "started":
                result.started_at = now
            if verbose and event["type"] != "progress":
                shown = {k: (v[:60] + "…" if k == "url" else v) for k, v in event.items()}
                print(f"{elapsed(now)}  {shown}")
            if event["type"] in ("done", "error", "cancelled"):
                result.final, result.finished_at = event, now
                break
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
    parser.add_argument("text", nargs="?", default="Hello from the speech API. This is a test.")
    parser.add_argument("--long", action="store_true", help="use a long text")
    parser.add_argument("--voice", default="af_heart")
    parser.add_argument("--lang", default="a")
    parser.add_argument("--cancel-after", type=float, help="cancel after N seconds")
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()

    body = {"text": LONG_TEXT if args.long else args.text, "lang": args.lang, "voice": args.voice}
    result = asyncio.run(run(args.api, body, args.cancel_after))
    if not result.job_id:
        return 1

    print(f"\nreceived {result.chunks} audio chunk(s), {result.audio_seconds:.1f}s of speech")
    if result.final.get("type") == "done":
        total = result.finished_at - result.queued_at
        if result.chunks:
            print(f"total {total:.1f}s ({result.audio_seconds / total:.1f}x real time)")
        else:
            print(f"served from cache in {total:.2f}s (identical text and settings)")
        print("download:", check_download(result.final["url"]))
    return 0 if result.final.get("type") in ("done", "cancelled") else 1


if __name__ == "__main__":
    sys.exit(main())
