"""Postgres access (Supabase): job records, history, pronunciations and usage.

The API uses `PostgresDatabase` (async, pooled); the worker records results with
`record_result_sync`. Tests use the in-memory `MemoryDatabase` from server/tests.
Job text is never stored.
"""

from __future__ import annotations

import datetime as dt
from typing import Protocol


class Database(Protocol):
    async def insert_job(self, job: dict) -> None: ...

    async def history(self, user_id: str, since: dt.datetime) -> list[dict]: ...

    async def get_pronunciations(self, user_id: str) -> list[dict]: ...

    async def put_pronunciations(self, user_id: str, entries: list[dict]) -> None: ...

    async def add_usage(self, subject: str, day: dt.date, chars: int) -> None: ...

    async def close(self) -> None: ...


JOB_COLUMNS = (
    "id", "user_id", "anon_id", "status", "lang", "voice", "blend_voice", "blend_ratio",
    "speed", "pitch", "chars", "audio_seconds", "storage_key", "wav_key", "cached",
    "finished_at",
)  # fmt: skip

HISTORY_COLUMNS = (
    "id", "status", "lang", "voice", "blend_voice", "blend_ratio", "speed", "pitch",
    "chars", "audio_seconds", "storage_key", "wav_key", "created_at",
)  # fmt: skip


class PostgresDatabase:
    def __init__(self, pool):
        self._pool = pool

    @classmethod
    async def connect(cls, url: str) -> PostgresDatabase:
        from psycopg_pool import AsyncConnectionPool

        pool = AsyncConnectionPool(url, min_size=1, max_size=5, open=False)
        await pool.open(wait=True, timeout=10)
        return cls(pool)

    async def insert_job(self, job: dict) -> None:
        columns = [c for c in JOB_COLUMNS if c in job]
        placeholders = ", ".join(f"%({c})s" for c in columns)
        async with self._pool.connection() as conn:
            await conn.execute(
                f"insert into public.jobs ({', '.join(columns)}) values ({placeholders})",  # noqa: S608 (fixed column names)
                job,
            )

    async def history(self, user_id: str, since: dt.datetime) -> list[dict]:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                f"select {', '.join(HISTORY_COLUMNS)} from public.jobs"  # noqa: S608
                " where user_id = %s and created_at >= %s and status = 'done'"
                " order by created_at desc limit 200",
                (user_id, since),
            )
            return [dict(zip(HISTORY_COLUMNS, row, strict=True)) for row in await cur.fetchall()]

    async def get_pronunciations(self, user_id: str) -> list[dict]:
        async with self._pool.connection() as conn:
            cur = await conn.execute(
                "select word, say from public.pronunciations where user_id = %s order by word",
                (user_id,),
            )
            return [{"word": w, "say": s} for w, s in await cur.fetchall()]

    async def put_pronunciations(self, user_id: str, entries: list[dict]) -> None:
        async with self._pool.connection() as conn, conn.transaction():
            await conn.execute("delete from public.pronunciations where user_id = %s", (user_id,))
            if entries:
                async with conn.cursor() as cur:
                    await cur.executemany(
                        "insert into public.pronunciations (user_id, word, say)"
                        " values (%s, %s, %s)",
                        [(user_id, e["word"], e["say"]) for e in entries],
                    )

    async def add_usage(self, subject: str, day: dt.date, chars: int) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(
                "insert into public.usage_daily (subject, day, chars, jobs) values (%s, %s, %s, 1)"
                " on conflict (subject, day) do update"
                " set chars = usage_daily.chars + excluded.chars, jobs = usage_daily.jobs + 1",
                (subject, day, chars),
            )

    async def close(self) -> None:
        await self._pool.close()


def record_result_sync(url: str):
    """A function the worker calls with each job's final state (one connection, reused)."""
    import psycopg

    state = {"conn": None}

    def record(job_id: str, status: str, **fields) -> None:
        if state["conn"] is None or state["conn"].closed:
            state["conn"] = psycopg.connect(url, autocommit=True)
        state["conn"].execute(
            "update public.jobs set status = %s, audio_seconds = %s, storage_key = %s,"
            " wav_key = %s, error = %s, finished_at = now() where id = %s",
            (
                status,
                fields.get("audio_seconds"),
                fields.get("storage_key"),
                fields.get("wav_key"),
                fields.get("error"),
                job_id,
            ),
        )

    return record
