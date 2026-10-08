"""Accounts (M5): tiers, daily quota, bot check, history, pronunciations, tokens."""

import pytest
from fastapi import WebSocketDisconnect

from server.tests.api.conftest import ALICE
from server.tests.api.conftest import create as _create
from server.tests.api.conftest import work as _work

BOB = "user:22222222-2222-2222-2222-222222222222:bob@example.com"
ALICE_ID = "11111111-1111-1111-1111-111111111111"


# ── Who am I ─────────────────────────────────────────────────────────────────
def test_me_for_visitors_and_users(env):
    with env.client() as visitor:
        me = visitor.get("/v1/me").json()
    assert me["signed_in"] is False and me["email"] is None
    assert me["limits"] == {
        "max_chars": 2000,
        "daily_chars": 10_000,
        "max_active_jobs": 2,
        "uploads": False,
        "wav": False,
    }
    with env.client(ALICE) as alice:
        me = alice.get("/v1/me").json()
    assert me["signed_in"] is True and me["email"] == "alice@example.com"
    assert me["limits"]["max_chars"] == 20_000 and me["limits"]["wav"] is True


def test_an_invalid_token_is_refused_not_treated_as_anonymous(env):
    with env.client("garbage-token") as client:
        response = client.get("/v1/me")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"
        assert _create(client).status_code == 401


# ── Bot check ────────────────────────────────────────────────────────────────
def test_visitors_need_to_pass_the_bot_check(env):
    with env.client() as visitor:
        refused = _create(visitor, turnstile_token=None)
        assert refused.status_code == 401
        assert "robot" in refused.json()["error"]["message"]
        assert _create(visitor, turnstile_token="human").status_code == 201


def test_signed_in_users_skip_the_bot_check(env):
    with env.client(ALICE) as alice:
        assert _create(alice, turnstile_token=None).status_code == 201


# ── Limits ───────────────────────────────────────────────────────────────────
def test_users_get_longer_texts(env):
    with env.client() as visitor:
        too_long = _create(visitor, text="x" * 2001)
    assert too_long.status_code == 413
    assert "Sign in for up to 20,000" in too_long.json()["error"]["message"]
    with env.client(ALICE) as alice:
        assert _create(alice, text="x" * 2001).status_code == 201


def test_daily_quota_counts_generated_characters(env):
    env.settings.anon_daily_chars = 30
    env.settings.max_active_jobs = 10
    with env.client() as visitor:
        assert _create(visitor, text="a" * 20).status_code == 201
        assert visitor.get("/v1/me").json()["chars_today"] == 20
        over = _create(visitor, text="b" * 15)
        assert over.status_code == 429
        error = over.json()["error"]
        assert error["code"] == "quota_exceeded"
        assert "remaining 10 characters" in error["message"]
        assert _create(visitor, text="c" * 10).status_code == 201  # still fits


def test_cached_results_do_not_use_the_quota(env):
    env.settings.anon_daily_chars = 25
    with env.client() as visitor:
        job_id = _create(visitor, text="d" * 20).json()["id"]
        _work(env, job_id)
        again = _create(visitor, text="d" * 20)  # served from the cache
        assert again.json()["status"] == "done"
        assert visitor.get("/v1/me").json()["chars_today"] == 20


def test_users_are_rate_limited_per_account_not_per_ip(env):
    env.settings.user_rate_limit_per_minute = 2
    env.settings.user_max_active_jobs = 10
    with env.client(ALICE) as alice, env.client(BOB) as bob:
        assert _create(alice, text="1.").status_code == 201
        assert _create(alice, text="2.").status_code == 201
        assert _create(alice, text="3.").status_code == 429
        assert _create(bob, text="4.").status_code == 201  # same IP, different account


# ── Records, WAV and history ─────────────────────────────────────────────────
def test_jobs_are_recorded_without_their_text(env):
    with env.client(ALICE) as alice:
        job_id = _create(alice, text="A secret sentence.").json()["id"]
    row = env.db.jobs[job_id]
    assert row["user_id"] == ALICE_ID and row["anon_id"] is None
    assert row["chars"] == len("A secret sentence.")
    assert "secret" not in str(row)
    usage = env.db.usage[(f"users:{ALICE_ID}", next(iter(env.db.usage))[1])]
    assert usage == {"chars": 18, "jobs": 1}


def test_signed_in_users_get_a_wav_and_a_history(env):
    with env.client(ALICE) as alice:
        job_id = _create(alice).json()["id"]
        _work(env, job_id)
        job = alice.get(f"/v1/tts/jobs/{job_id}").json()
        assert job["url"].endswith(".mp3?signature=abc")
        assert job["wav_url"].endswith(".wav?signature=abc")
        assert env.db.jobs[job_id]["status"] == "done"  # recorded by the worker

        history = alice.get("/v1/me/history").json()
    assert history["days"] == 7
    [item] = history["items"]
    assert item["id"] == job_id and item["voice"] == "af_heart" and item["audio_seconds"] == 0.3
    assert item["url"] and item["wav_url"]

    with env.client(BOB) as bob:
        assert bob.get("/v1/me/history").json()["items"] == []
    with env.client() as visitor:
        assert visitor.get("/v1/me/history").status_code == 401


# ── Pronunciations ───────────────────────────────────────────────────────────
def test_saved_pronunciations_apply_to_new_jobs(env):
    entries = [{"word": "Kokoro", "say": "/kˈOkəɹO/"}, {"word": "NYC", "say": "New York City"}]
    with env.client(ALICE) as alice:
        saved = alice.put("/v1/me/pronunciations", json={"entries": entries})
        assert saved.status_code == 200
        assert alice.get("/v1/me/pronunciations").json() == {"entries": entries}
        _create(alice, text="Kokoro in NYC.")
    assert env.queue.jobs[-1][1]["pronunciations"] == entries


def test_pronunciations_reject_duplicate_words_and_need_an_account(env):
    duplicate = [{"word": "Hi", "say": "hey"}, {"word": "hi", "say": "high"}]
    with env.client(ALICE) as alice:
        response = alice.put("/v1/me/pronunciations", json={"entries": duplicate})
    assert response.status_code == 422
    assert "only have one" in response.json()["error"]["message"]
    with env.client() as visitor:
        assert visitor.get("/v1/me/pronunciations").status_code == 401


def test_changed_pronunciations_are_not_served_from_the_cache(env):
    with env.client() as visitor:
        job_id = _create(visitor, text="Kokoro.").json()["id"]
        _work(env, job_id)
        again = _create(
            visitor, text="Kokoro.", pronunciations=[{"word": "Kokoro", "say": "cocoa"}]
        )
        assert again.json()["status"] == "queued"


# ── Streaming with a token ───────────────────────────────────────────────────
def test_stream_accepts_a_token_as_a_subprotocol(env):
    with env.client(ALICE) as alice:
        job_id = _create(alice).json()["id"]
        _work(env, job_id)
        alice.headers.pop("Authorization")  # browsers can't send headers on WebSockets
        url = f"/v1/tts/jobs/{job_id}/stream"
        with alice.websocket_connect(url, subprotocols=["kokoro", f"auth.{ALICE}"]) as ws:
            assert ws.accepted_subprotocol == "kokoro"
            assert ws.receive_json()["type"] == "started"

        with (
            pytest.raises(WebSocketDisconnect) as stranger,
            alice.websocket_connect(url, subprotocols=["kokoro", f"auth.{BOB}"]) as ws,
        ):
            ws.receive_json()
        assert stranger.value.code == 4404

        with (
            pytest.raises(WebSocketDisconnect) as expired,
            alice.websocket_connect(url, subprotocols=["kokoro", "auth.expired"]) as ws,
        ):
            ws.receive_json()
        assert expired.value.code == 4401
