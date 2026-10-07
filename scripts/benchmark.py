"""Benchmark the workers: many jobs at once, like a busy minute.

With the docker compose stack running:

    python scripts/benchmark.py --jobs 8

Half the jobs are short (one sentence, short queue), half are long paragraphs
(long queue), all sent at once through the API. Each text is made unique so the
result cache doesn't skew the numbers. Reports time to first audio for short and
long jobs separately, and overall throughput.
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

SHORT_TEXT = "Thanks for calling. Your order has shipped and will arrive on Thursday."


def _p(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))]


async def bench(api: str, jobs: int) -> None:
    run_id = int(time.time())
    bodies = [
        {"text": (SHORT_TEXT if i % 2 == 0 else LONG_TEXT) + f" Run {run_id}, job {i}."}
        for i in range(jobs)
    ]
    started = time.perf_counter()
    results = await asyncio.gather(*(run(api, body, verbose=False) for body in bodies))
    wall = time.perf_counter() - started

    ok = [r for r in results if r.final.get("type") == "done"]
    failed = [r.final for r in results if r.final.get("type") != "done"]
    print(
        f"{len(ok)} of {jobs} jobs done in {wall:.1f}s" + (f"; failed: {failed}" if failed else "")
    )
    if not ok:
        return

    def stats(name: str, values: list[float]) -> None:
        if values:
            print(
                f"{name:30} median {statistics.median(values):6.2f}s   "
                f"p95 {_p(values, 95):6.2f}s   max {max(values):6.2f}s"
            )

    short = [
        r
        for r, b in zip(results, bodies, strict=True)
        if r in ok and b["text"].startswith(SHORT_TEXT)
    ]
    long = [r for r in ok if r not in short]
    stats("first audio, short jobs", [r.first_audio_at - r.queued_at for r in short])
    stats("first audio, long jobs", [r.first_audio_at - r.queued_at for r in long])
    stats("total per job", [r.finished_at - r.queued_at for r in ok])
    audio = sum(r.audio_seconds for r in ok)
    print(
        f"{'throughput':30} {audio:.0f}s of speech in {wall:.1f}s = {audio / wall:.1f}x real time"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jobs", type=int, default=8)
    parser.add_argument("--api", default="http://localhost:8000")
    args = parser.parse_args()
    asyncio.run(bench(args.api, args.jobs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
