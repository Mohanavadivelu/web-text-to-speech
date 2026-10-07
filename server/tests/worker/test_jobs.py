import threading
import time

import fakeredis
import pytest

from server import events
from server.config import Settings
from server.tests.fakes import FakeEngine, FakeStorage
from server.worker.jobs import JobRequest, job_timeout, run_job
from server.worker.storage import audio_key

SETTINGS = Settings(_env_file=None, min_job_timeout_seconds=60)


@pytest.fixture
def redis():
    return fakeredis.FakeRedis()


def _replay(redis, job_id):
    return [events.decode(m) for m in redis.lrange(events.log_key(job_id), 0, -1)]


def _run(redis, engine=None, storage=None, request=None, job_id="job1"):
    return run_job(
        job_id,
        request or JobRequest(text="Hello there.", lang="a", voice="af_heart"),
        engine=engine or FakeEngine(),
        storage=storage or FakeStorage(),
        redis=redis,
        settings=SETTINGS,
    )


def test_successful_job_streams_audio_and_stores_an_mp3(redis):
    storage = FakeStorage()
    final = _run(redis, storage=storage)

    key = audio_key("anon", "local", "job1")
    assert final == {"type": "done", "duration": 0.3}
    assert storage.objects[key][1] == "audio/mpeg"

    replay = _replay(redis, "job1")
    assert replay[0] == (
        "event",
        {"type": "started", "sample_rate": 24000, "estimated_seconds": 0.9},
    )
    audio = [body for kind, body in replay if kind == "audio"]
    assert len(audio) == 3 and all(len(a) == 2400 * 2 for a in audio)  # PCM16
    assert ("event", {"type": "progress", "percent": 100}) in replay
    assert replay[-1] == ("event", final)

    record = redis.hgetall(events.record_key("job1"))
    assert record[b"status"] == b"done"
    assert record[b"key"] == key.encode()
    assert record[b"audio_seconds"] == b"0.3"


def test_engine_gets_the_short_first_segment_setting(redis):
    engine = FakeEngine()
    _run(redis, engine=engine)
    assert engine.calls[0]["first_segment_chars"] == SETTINGS.first_segment_chars


def test_wav_copy_is_stored_when_requested(redis):
    storage = FakeStorage()
    _run(
        redis, storage=storage, request=JobRequest(text="Hi.", lang="a", voice="af_heart", wav=True)
    )
    assert storage.objects[audio_key("anon", "local", "job1", "wav")][1] == "audio/wav"


def test_cancel_request_stops_the_job(redis):
    threading.Timer(0.2, lambda: redis.set(events.cancel_key("job1"), 1)).start()
    started = time.monotonic()
    final = _run(redis, engine=FakeEngine(chunks=50, delay=0.1))
    assert final == {"type": "cancelled"}
    assert time.monotonic() - started < 1.0
    assert redis.hget(events.record_key("job1"), "status") == b"cancelled"


def test_job_that_runs_too_long_is_stopped(redis, monkeypatch):
    monkeypatch.setattr("server.worker.jobs.job_timeout", lambda *a: 0.3)
    final = _run(redis, engine=FakeEngine(chunks=50, delay=0.1))
    assert final["type"] == "error"
    assert "too long" in final["message"]


def test_invalid_input_message_reaches_the_user(redis):
    final = _run(redis, engine=FakeEngine(error=ValueError("speed must be between 0.5 and 2.")))
    assert final == {"type": "error", "message": "speed must be between 0.5 and 2."}
    assert redis.hget(events.record_key("job1"), "error") == b"speed must be between 0.5 and 2."


def test_unexpected_errors_are_hidden_from_the_user(redis):
    final = _run(redis, engine=FakeEngine(error=RuntimeError("secret internal detail")))
    assert final["type"] == "error"
    assert "secret" not in final["message"]


def test_storage_failure_still_ends_the_job(redis):
    final = _run(redis, storage=FakeStorage(fail=True))
    assert final["type"] == "error"
    assert _replay(redis, "job1")[-1] == ("event", final)


def test_finished_job_is_remembered_for_identical_requests(redis):
    request = JobRequest(text="Hi.", lang="a", voice="af_heart", cache_key="abc123")
    _run(redis, request=request)
    assert (
        redis.get(events.cache_entry_key("abc123"))
        == (audio_key("anon", "local", "job1") + "|0.3").encode()
    )
    assert 0 < redis.ttl(events.cache_entry_key("abc123")) <= SETTINGS.cache_ttl_seconds


def test_retried_job_starts_a_fresh_replay(redis):
    _run(redis)
    _run(redis)
    started = [
        e for kind, e in _replay(redis, "job1") if kind == "event" and e["type"] == "started"
    ]
    assert len(started) == 1


def test_timeout_is_at_least_the_minimum_and_grows_with_text():
    engine = FakeEngine()
    short = JobRequest(text="Hi.", lang="a", voice="af_heart")
    long = JobRequest(text="word " * 20_000, lang="a", voice="af_heart")
    assert job_timeout(short, engine, SETTINGS) == 60
    assert job_timeout(long, engine, SETTINGS) > 60
