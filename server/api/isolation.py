"""Run document parsing in a separate, short-lived process.

Uploaded files are untrusted: a crafted PDF can make a parser loop for a long time
or use a lot of memory. Each extraction runs in its own process with a time limit
and (on Linux) a memory limit, and the process is killed if it goes over.
"""

from __future__ import annotations

import asyncio
import multiprocessing as mp
import sys

from server.engine.text import ExtractError

MEMORY_LIMIT_BYTES = 768 * 1024 * 1024
MAX_PARALLEL = 2  # extractions at once per API process; more wait their turn

_slots: asyncio.Semaphore | None = None


def _child(conn, data: bytes, filename: str) -> None:
    if sys.platform.startswith("linux"):
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    try:
        from server.engine.text import extract_text

        conn.send(("ok", extract_text(data, filename)))
    except ExtractError as exc:
        conn.send(("user_error", str(exc)))
    except MemoryError:
        conn.send(("user_error", "This document is too complex to open."))
    except Exception as exc:  # anything else is a damaged file from the user's point of view
        conn.send(("user_error", f"This file couldn't be read ({type(exc).__name__})."))
    finally:
        conn.close()


def _run(data: bytes, filename: str, timeout: float) -> tuple[str, bool]:
    ctx = mp.get_context("spawn")  # a clean interpreter: no inherited sockets or state
    parent, child = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_child, args=(child, data, filename), daemon=True)
    process.start()
    child.close()
    try:
        if not parent.poll(timeout):
            raise ExtractError("This document took too long to open.")
        status, payload = parent.recv()
    except EOFError:
        raise ExtractError("This document is too complex to open.") from None
    finally:
        if process.is_alive():
            process.kill()
        process.join(timeout=5)
        parent.close()
    if status != "ok":
        raise ExtractError(payload)
    return payload


async def extract_isolated(data: bytes, filename: str, timeout: float) -> tuple[str, bool]:
    """extract_text() in a separate process; raises ExtractError with a user-safe message."""
    global _slots
    if _slots is None:
        _slots = asyncio.Semaphore(MAX_PARALLEL)
    async with _slots:
        return await asyncio.to_thread(_run, data, filename, timeout)
