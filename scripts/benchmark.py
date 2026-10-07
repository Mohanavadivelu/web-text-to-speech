"""Benchmark the workers: many jobs at once, like a busy minute.

With the docker compose stack running (scale workers first if you like):

    docker compose -f server/docker-compose.yml up -d --scale worker=2
    python scripts/benchmark.py --jobs 8

Half the jobs are short (one sentence), half are long paragraphs. Reports queue
wait, time to first audio and overall throughput.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.try_job import LONG_TEXT, run  # noqa: E402
from server.worker.jobs import JobRequest  # noqa: E402

SHORT_TEXT = "Thanks for calling. Your order has shipped and will arrive on Thursday."


def _p(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))]


async def bench(redis_url: str, jobs: int) -> None:
    requests = [
        JobRequest(text=SHORT_TEXT if i % 2 == 0 else LONG_TEXT[:2000], lang="a", voice="af_heart")
        for i in range(jobs)
    ]
    started = time.perf_counter()
    results = await asyncio.gather(*(run(redis_url, r, verbose=False) for r in requests))
    wall = time.perf_counter() - started

    failed = [r for r in results if r.final.get("type") != "done"]
    ok = [r for r in results if r.final.get("type") == "done"]
    if not ok:
        print("all jobs failed:", [r.final for r in failed])
        return

    def stats(name: str, values: list[float]) -> None:
        print(
            f"{name:22} median {statistics.median(values):6.2f}s   "
            f"p95 {_p(values, 95):6.2f}s   max {max(values):6.2f}s"
        )

    print(
        f"{len(ok)} of {jobs} jobs done in {wall:.1f}s"
        + (f", {len(failed)} failed" if failed else "")
    )
    stats("queue wait", [r.started_at - r.queued_at for r in ok])
    stats("time to first audio", [r.first_audio_at - r.queued_at for r in ok])
    stats("total per job", [r.finished_at - r.queued_at for r in ok])
    audio = sum(r.audio_seconds for r in ok)
    print(
        f"{'throughput':22} {audio:.0f}s of speech in {wall:.1f}s = {audio / wall:.1f}x real time"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--redis", default="redis://localhost:6379/0")
    args = parser.parse_args()
    asyncio.run(bench(args.redis, args.jobs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
