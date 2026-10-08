import json
import threading

import fakeredis
import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from server import events
from server.api.deps import Services
from server.api.main import create_app
from server.config import Settings
from server.tests.fakes import FakeEngine, FakeQueue, FakeStorage
from server.worker.jobs import JobRequest, run_job

SHORT = "Hello there."


class Env:
    """Shared fake Redis server, queue and storage; each client gets its own connection."""

    def __init__(self):
        self.server = fakeredis.FakeServer()
        self.settings = Settings(_env_file=None, rate_limit_per_minute=1000)
        self.queue = FakeQueue()
        self.storage = FakeStorage()
        self.redis = fakeredis.FakeRedis(server=self.server)  # the worker's (sync) view

    def client(self) -> TestClient:
        svc = Services(
            settings=self.settings,
            redis=fakeredis.FakeAsyncRedis(server=self.server),
            queue=self.queue,
            storage=self.storage,
        )
        return TestClient(create_app(svc))


@pytest.fixture
def env():
    return Env()


@pytest.fixture
def client(env):
    with env.client() as c:
        yield c


def _other_client(env):
    return env.client()


def _work(env, job_id, engine=None):
    """Do what a worker does with the job that was queued."""
    _, request, _ = next(j for j in env.queue.jobs if j[0] == job_id)
    return run_job(
        job_id,
        JobRequest(**request),
        engine=engine or FakeEngine(),
        storage=env.storage,
        redis=env.redis,
        settings=env.settings,
    )


def _create(client, **body):
    return client.post("/v1/tts/jobs", json={"text": SHORT} | body)


# ── Meta ─────────────────────────────────────────────────────────────────────
def test_health_needs_a_live_worker(client, env):
    assert client.get("/v1/health").status_code == 503
    env.redis.set(events.WORKER_HEARTBEAT_PREFIX + "w1", 1)
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "redis": "ok", "workers": 1}


def test_voices(client):
    body = client.get("/v1/voices").json()
    assert len(body["languages"]) == 7
    assert sum(len(lang["voices"]) for lang in body["languages"]) == 37
    english = body["languages"][0]
    assert english["code"] == "a" and english["default_voice"] == "af_heart"
    assert body["speed"] == [0.5, 2.0]


def test_config_tells_the_web_app_its_limits(client):
    assert client.get("/v1/config").json() == {
        "max_chars": 2000,
        "max_upload_mb": 5,
        "document_types": [".txt", ".md", ".docx", ".pdf"],
    }


def test_responses_carry_a_request_id(client):
    assert client.get("/v1/voices").headers["X-Request-ID"]
    assert (
        client.get("/v1/voices", headers={"X-Request-ID": "abc"}).headers["X-Request-ID"] == "abc"
    )


def test_unknown_route_uses_the_error_format(client):
    response = client.get("/v1/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# ── Creating jobs ────────────────────────────────────────────────────────────
def test_create_job_queues_it_and_sets_a_cookie(client, env):
    response = _create(client, voice="af_bella", speed=1.2)
    assert response.status_code == 201
    job = response.json()
    assert job["status"] == "queued"
    assert job["queue_position"] == 0
    assert job["stream_url"] == f"/v1/tts/jobs/{job['id']}/stream"
    assert "anon_id" in response.cookies

    job_id, request, queue = env.queue.jobs[0]
    assert job_id == job["id"]
    assert queue == "tts:short"
    assert request["voice"] == "af_bella" and request["speed"] == 1.2
    assert request["owner_kind"] == "anon" and request["cache_key"]


def test_long_texts_go_to_the_long_queue(env):
    env.settings.anon_max_chars = 5000
    with env.client() as c:
        assert _create(c, text="word " * 300).status_code == 201
    assert env.queue.jobs[0][2] == "tts:long"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"voice": "bf_emma"}, "doesn't belong"),
        ({"voice": "nobody"}, "Unknown voice"),
        ({"speed": 3}, "speed"),
        ({"pitch": -9}, "pitch"),
        ({"text": "   "}, "no text"),
    ],
)
def test_invalid_jobs_are_rejected_with_a_clear_message(client, body, message):
    response = _create(client, **body)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_input"
    assert message in error["message"]


def test_text_over_the_limit(client):
    response = _create(client, text="x" * 2001)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "too_long"


def test_only_two_active_jobs_per_visitor(client, env):
    assert _create(client).status_code == 201
    assert _create(client, text="Second.").status_code == 201
    third = _create(client, text="Third.")
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "rate_limited"

    _work(env, env.queue.jobs[0][0])  # first job finishes
    assert _create(client, text="Fourth.").status_code == 201


def test_rate_limit_per_minute(env):
    env.settings.rate_limit_per_minute = 2
    env.settings.max_active_jobs = 100
    with env.client() as c:
        assert _create(c, text="1.").status_code == 201
        assert _create(c, text="2.").status_code == 201
        limited = _create(c, text="3.")
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0


def test_busy_when_the_queue_is_full(env):
    env.settings.max_queued_jobs = 1
    with env.client() as c:
        assert _create(c).status_code == 201
    with _other_client(env) as other:
        busy = _create(other)
    assert busy.status_code == 503
    assert busy.json()["error"]["code"] == "busy"


# ── Checking and cancelling ──────────────────────────────────────────────────
def test_finished_job_has_a_download_link(client, env):
    job_id = _create(client).json()["id"]
    _work(env, job_id)
    job = client.get(f"/v1/tts/jobs/{job_id}").json()
    assert job["status"] == "done"
    assert job["progress"] == 100
    assert job["audio_seconds"] == 0.3
    assert job["url"].startswith("https://storage.test/audio/anon/")


def test_jobs_are_private_to_their_owner(client, env):
    job_id = _create(client).json()["id"]
    with _other_client(env) as stranger:
        assert stranger.get(f"/v1/tts/jobs/{job_id}").status_code == 404
        assert stranger.delete(f"/v1/tts/jobs/{job_id}").status_code == 404
    assert client.get("/v1/tts/jobs/j_doesnotexist").status_code == 404


def test_forged_cookie_is_not_accepted(client, env):
    job_id = _create(client).json()["id"]
    anon_id = client.cookies["anon_id"].split(".")[0]
    with _other_client(env) as forger:
        forger.cookies.set("anon_id", f"{anon_id}.{'0' * 32}")
        assert forger.get(f"/v1/tts/jobs/{job_id}").status_code == 404


def test_cancel_stops_the_worker(client, env):
    job_id = _create(client).json()["id"]
    assert client.delete(f"/v1/tts/jobs/{job_id}").status_code == 202
    assert env.redis.exists(events.cancel_key(job_id))
    final = _work(env, job_id, engine=FakeEngine(chunks=20, delay=0.05))
    assert final == {"type": "cancelled"}
    assert client.get(f"/v1/tts/jobs/{job_id}").json()["status"] == "cancelled"


# ── Streaming ────────────────────────────────────────────────────────────────
def test_stream_delivers_audio_live_and_a_link_at_the_end(client, env):
    job_id = _create(client).json()["id"]
    worker = threading.Timer(0.2, _work, args=(env, job_id))  # starts after we connect
    worker.start()
    with client.websocket_connect(f"/v1/tts/jobs/{job_id}/stream") as ws:
        received = _receive_all(ws)
    worker.join()
    assert received[0][1]["type"] == "started"
    assert [len(body) for kind, body in received if kind == "audio"] == [4800, 4800, 4800]
    done = received[-1][1]
    assert done["url"].startswith("https://storage.test/") and done["duration"] == 0.3


def _receive_all(ws) -> list:
    """Every message until the final event: ("audio", bytes) or ("event", dict)."""
    received = []
    while True:
        message = ws.receive()
        if message.get("bytes") is not None:
            received.append(("audio", message["bytes"]))
            continue
        event = json.loads(message["text"])
        received.append(("event", event))
        if event["type"] in events.FINAL_EVENTS:
            return received


def test_late_listener_gets_everything_from_the_start(client, env):
    job_id = _create(client).json()["id"]
    _work(env, job_id)  # finished before anyone listened
    with client.websocket_connect(f"/v1/tts/jobs/{job_id}/stream") as ws:
        received = _receive_all(ws)
    assert received[0] == (
        "event",
        {"type": "started", "sample_rate": 24000, "estimated_seconds": 0.9},
    )
    assert [len(body) for kind, body in received if kind == "audio"] == [4800, 4800, 4800]
    assert received[-1][1]["type"] == "done"


def test_stream_refuses_strangers(client, env):
    job_id = _create(client).json()["id"]
    with (
        _other_client(env) as stranger,
        pytest.raises(WebSocketDisconnect) as closed,
        stranger.websocket_connect(f"/v1/tts/jobs/{job_id}/stream") as ws,
    ):
        ws.receive_json()
    assert closed.value.code == 4404


# ── Cache ────────────────────────────────────────────────────────────────────
def test_identical_request_reuses_the_finished_audio(client, env):
    job_id = _create(client).json()["id"]
    _work(env, job_id)
    with _other_client(env) as someone_else:
        again = _create(someone_else)
        assert again.status_code == 201
        job = again.json()
        assert job["status"] == "done" and job["url"]
        assert len(env.queue.jobs) == 1  # no second job for the worker
        with someone_else.websocket_connect(job["stream_url"]) as ws:
            assert ws.receive_json()["type"] == "started"
            assert ws.receive_json()["type"] == "done"
    # the copy lives in the new caller's own folder
    assert sum(1 for k in env.storage.objects if k.startswith("audio/anon/")) == 2


def test_different_settings_are_not_reused(client, env):
    job_id = _create(client).json()["id"]
    _work(env, job_id)
    assert _create(client, speed=1.5).json()["status"] == "queued"


# ── Text and files ───────────────────────────────────────────────────────────
def test_clean_text(client):
    response = client.post("/v1/text/clean", json={"text": "“Hi”  see www.example.org."})
    assert response.json() == {"text": '"Hi" see.'}


def test_extract_a_text_file(client):
    response = client.post("/v1/files/extract", files={"file": ("note.txt", b"Hello file.")})
    assert response.status_code == 200
    assert response.json() == {"text": "Hello file.", "cleaned": False, "characters": 11}


def test_extract_rejects_bad_and_huge_files(client, env):
    fake_pdf = client.post("/v1/files/extract", files={"file": ("x.pdf", b"not a pdf")})
    assert fake_pdf.status_code == 422
    assert "isn't a real PDF" in fake_pdf.json()["error"]["message"]

    env.settings.max_upload_bytes = 10
    huge = client.post("/v1/files/extract", files={"file": ("big.txt", b"x" * 11)})
    assert huge.status_code == 413


def test_long_audio_is_sent_in_one_second_frames(client, env):
    job_id = _create(client).json()["id"]
    _work(env, job_id, engine=FakeEngine(chunks=1, chunk_seconds=2.5))
    with client.websocket_connect(f"/v1/tts/jobs/{job_id}/stream") as ws:
        received = _receive_all(ws)
    assert [len(body) for kind, body in received if kind == "audio"] == [48_000, 48_000, 24_000]
