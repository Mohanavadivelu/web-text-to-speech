"""Shared test setup.

Tests marked `slow` need the Kokoro model files. They are skipped when the files
are missing, unless REQUIRE_MODELS=1 is set (as in the CI engine job), in which
case missing files fail the run instead of hiding the tests.
"""

import os

import pytest

from server.engines.kokoro import model_store


def _models_present() -> bool:
    return not model_store.problems(check_hashes=False)


def pytest_collection_modifyitems(config, items):
    if _models_present():
        return
    if os.environ.get("REQUIRE_MODELS") == "1":
        raise pytest.UsageError(
            "REQUIRE_MODELS=1 but the model files are missing: "
            "run `python -m server.engines.kokoro.model_store download`."
        )
    skip = pytest.mark.skip(reason="model files not downloaded")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def engine():
    from server.engines.kokoro.synth import KokoroEngine

    eng = KokoroEngine()
    eng.load()
    return eng
