import pytest

from server import events
from server.config import Settings
from server.worker.storage import audio_key


def test_audio_keys():
    assert audio_key("users", "u-123", "j_1") == "audio/users/u-123/j_1.mp3"
    assert audio_key("anon", "a1", "j_1", "wav") == "audio/anon/a1/j_1.wav"


@pytest.mark.parametrize(
    "args",
    [
        ("admins", "u1", "j1"),  # unknown owner kind
        ("users", "../other", "j1"),  # path traversal
        ("users", "u1", "j1/../../x"),
        ("users", "u1", "j1", "exe"),  # unknown format
    ],
)
def test_audio_key_rejects_unsafe_values(args):
    with pytest.raises(ValueError):
        audio_key(*args)


def test_event_encoding_round_trip():
    assert events.decode(events.encode_event({"type": "progress", "percent": 5})) == (
        "event",
        {"type": "progress", "percent": 5},
    )
    assert events.decode(events.encode_audio(b"\x01\x02")) == ("audio", b"\x01\x02")
    with pytest.raises(ValueError):
        events.decode(b"X???")


def test_storage_endpoints_default_to_r2_and_can_be_overridden():
    r2 = Settings(_env_file=None, r2_account_id="abc")
    assert r2.storage_endpoint == "https://abc.r2.cloudflarestorage.com"
    assert r2.storage_public_endpoint == r2.storage_endpoint

    dev = Settings(
        _env_file=None,
        r2_endpoint_url="http://seaweedfs:8333",
        r2_public_endpoint_url="http://localhost:8333",
    )
    assert dev.storage_endpoint == "http://seaweedfs:8333"
    assert dev.storage_public_endpoint == "http://localhost:8333"
