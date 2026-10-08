"""The real SQL: migrations, queries and row-level security, against Postgres.

Runs when TEST_DATABASE_URL points at a Postgres server (local Supabase works:
postgresql://postgres:postgres@127.0.0.1:54322/postgres). Each run creates a
throwaway database, applies supabase/migrations, and drops it afterwards.
"""

import asyncio
import datetime as dt
import os
import secrets
import uuid
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL not set"),
]

MIGRATIONS = Path(__file__).resolve().parents[3] / "supabase" / "migrations"
ALICE, BOB = str(uuid.uuid4()), str(uuid.uuid4())

# What Supabase provides and plain Postgres doesn't: the auth schema, auth.uid(), the
# "authenticated" role, and Supabase's default grants (RLS is what limits access).
SUPABASE_STUBS = """
do $$ begin
  if not exists (select from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin;
  end if;
end $$;
create schema if not exists auth;
create table if not exists auth.users (id uuid primary key, email text);
create or replace function auth.uid() returns uuid language sql stable as
  $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
"""
SUPABASE_GRANTS = """
grant usage on schema public to authenticated;
grant select on all tables in schema public to authenticated;
"""


def _with_db(url: str, name: str) -> str:
    base, _, _ = url.rpartition("/")
    return f"{base}/{name}"


@pytest.fixture(scope="module")
def database():
    name = "kokoro_test_" + secrets.token_hex(4)
    with psycopg.connect(URL, autocommit=True) as admin:
        admin.execute(f'create database "{name}"')
    url = _with_db(URL, name)
    try:
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(SUPABASE_STUBS)
            for migration in sorted(MIGRATIONS.glob("*.sql")):
                conn.execute(migration.read_text(encoding="utf-8"))
            conn.execute(SUPABASE_GRANTS)
            conn.execute(
                "insert into auth.users (id, email)"
                " values (%s, 'alice@x.test'), (%s, 'bob@x.test')",
                (ALICE, BOB),
            )
        yield url
    finally:
        with psycopg.connect(URL, autocommit=True) as admin:
            admin.execute(f'drop database if exists "{name}" with (force)')


def run(coroutine):
    # psycopg's async driver needs a selector event loop; Windows defaults to another kind
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        return runner.run(coroutine)


async def _db(url):
    from server.db import PostgresDatabase

    return await PostgresDatabase.connect(url)


def _job(job_id, **extra):
    return {
        "id": job_id, "status": "queued", "lang": "a", "voice": "af_heart", "speed": 1.0,
        "pitch": 0.0, "chars": 12,
    } | extra  # fmt: skip


def test_new_accounts_get_a_profile(database):
    with psycopg.connect(database) as conn:
        tiers = conn.execute("select tier from public.profiles where id = %s", (ALICE,)).fetchall()
    assert tiers == [("free",)]


def test_jobs_history_and_worker_results(database):
    from server.db import record_result_sync

    async def scenario():
        db = await _db(database)
        try:
            await db.insert_job(_job("j_alice1", user_id=ALICE))
            await db.insert_job(_job("j_alice2", user_id=ALICE))
            await db.insert_job(_job("j_anon1", anon_id="a123"))
            record = record_result_sync(database)
            record("j_alice1", "done", audio_seconds=3.5, storage_key="audio/users/x/j.mp3")
            record("j_alice2", "error", error="Something went wrong.")
            since = dt.datetime.now(dt.UTC) - dt.timedelta(days=7)
            return await db.history(ALICE, since), await db.history(BOB, since)
        finally:
            await db.close()

    alice, bob = run(scenario())
    assert [row["id"] for row in alice] == ["j_alice1"]  # finished jobs only
    assert alice[0]["audio_seconds"] == 3.5 and alice[0]["storage_key"].endswith(".mp3")
    assert bob == []


def test_a_job_needs_exactly_one_owner(database):
    async def scenario():
        db = await _db(database)
        try:
            await db.insert_job(_job("j_nobody"))
        finally:
            await db.close()

    with pytest.raises(psycopg.errors.CheckViolation):
        run(scenario())


def test_pronunciations_replace_and_usage_accumulates(database):
    async def scenario():
        db = await _db(database)
        try:
            await db.put_pronunciations(
                ALICE, [{"word": "A", "say": "ay"}, {"word": "B", "say": "bee"}]
            )
            await db.put_pronunciations(ALICE, [{"word": "C", "say": "see"}])
            day = dt.date(2026, 10, 8)
            await db.add_usage(f"users:{ALICE}", day, 100)
            await db.add_usage(f"users:{ALICE}", day, 50)
            return await db.get_pronunciations(ALICE)
        finally:
            await db.close()

    assert run(scenario()) == [{"word": "C", "say": "see"}]
    with psycopg.connect(database) as conn:
        usage = conn.execute("select chars, jobs from public.usage_daily").fetchall()
    assert usage == [(150, 2)]


def test_row_level_security_shows_users_only_their_own_rows(database):
    with psycopg.connect(database, autocommit=True) as conn:
        conn.execute(
            "insert into public.jobs (id, status, lang, voice, speed, pitch, chars, user_id)"
            " values ('j_bob', 'done', 'a', 'af_heart', 1, 0, 5, %s)",
            (BOB,),
        )
        conn.execute("insert into public.pronunciations values (%s, 'Bob', 'bobby')", (BOB,))

    def visible(user_id: str | None, table: str) -> list:
        with psycopg.connect(database) as conn:
            conn.execute("set role authenticated")
            if user_id:
                conn.execute("select set_config('request.jwt.claim.sub', %s, true)", (user_id,))
            column = {"jobs": "id", "profiles": "id", "usage_daily": "subject"}.get(
                table, "user_id"
            )
            rows = conn.execute(f"select {column} from public.{table}").fetchall()  # noqa: S608
            return [str(r[0]) for r in rows]

    assert visible(BOB, "jobs") == ["j_bob"]
    assert "j_bob" not in visible(ALICE, "jobs")
    assert visible(ALICE, "pronunciations") == [ALICE] * len(visible(ALICE, "pronunciations"))
    assert BOB not in visible(ALICE, "pronunciations")
    assert visible(ALICE, "profiles") == [ALICE]
    assert visible(None, "jobs") == []  # no user: nothing
    assert visible(ALICE, "usage_daily") == []  # no policy: nobody reads usage
