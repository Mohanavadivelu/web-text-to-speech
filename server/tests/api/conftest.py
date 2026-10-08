"""Shared setup for the API tests: fake services and helpers."""

import fakeredis
import pytest
from fastapi.testclient import TestClient

from server.api.deps import Services
from server.api.main import create_app
from server.config import Settings
from server.tests.fakes import (
    FakeBots,
    FakeDatabase,
    FakeEngine,
    FakeQueue,
    FakeStorage,
    FakeVerifier,
)
from server.worker.jobs import JobRequest, run_job

SHORT = "Hello there."


class Env:
    """Shared fake Redis server, queue and storage; each client gets its own connection."""

    def __init__(self):
        self.server = fakeredis.FakeServer()
        self.settings = Settings(_env_file=None, rate_limit_per_minute=1000)
        self.queue = FakeQueue()
        self.storage = FakeStorage()
        self.db = FakeDatabase()
        self.bots = FakeBots()
        self.redis = fakeredis.FakeRedis(server=self.server)  # the worker's (sync) view

    def client(self, token: str | None = None) -> TestClient:
        """A visitor; with a token ("user:<id>[:email]") a signed-in user."""
        svc = Services(
            settings=self.settings,
            redis=fakeredis.FakeAsyncRedis(server=self.server),
            queue=self.queue,
            storage=self.storage,
            db=self.db,
            verifier=FakeVerifier(),
            bots=self.bots,
        )
        client = TestClient(create_app(svc))
        if token:
            client.headers["Authorization"] = f"Bearer {token}"
        return client


@pytest.fixture
def env():
    return Env()


@pytest.fixture
def client(env):
    with env.client() as c:
        yield c


def other_client(env):
    return env.client()


def work(env, job_id, engine=None):
    """Do what a worker does with the job that was queued."""
    _, request, _ = next(j for j in env.queue.jobs if j[0] == job_id)
    return run_job(
        job_id,
        JobRequest(**request),
        engine=engine or FakeEngine(),
        storage=env.storage,
        redis=env.redis,
        settings=env.settings,
        on_finish=env.db.record_result,
    )


def create(client, **body):
    return client.post("/v1/tts/jobs", json={"text": SHORT, "turnstile_token": "human"} | body)


ALICE = "user:11111111-1111-1111-1111-111111111111:alice@example.com"
