import hashlib
import io

import pytest

from server.engines.kokoro import model_store
from server.engines.kokoro.model_store import RemoteFile


def test_manifest_covers_model_tokenizer_and_all_voices():
    from server.engines.kokoro.voices import VOICES

    paths = {f.repo_path for f in model_store.FILES}
    assert {"onnx/model.onnx", "tokenizer.json"} <= paths
    assert {f"voices/{v}.bin" for v in VOICES} <= paths
    assert len(model_store.FILES) == 2 + len(VOICES)
    assert all(len(f.sha256) == 64 for f in model_store.FILES)


def test_problems_reports_missing_and_damaged_files(tmp_path):
    assert len(model_store.problems(tmp_path)) == len(model_store.FILES)

    tokenizer = next(f for f in model_store.FILES if f.repo_path == "tokenizer.json")
    path = tokenizer.local_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x" * tokenizer.size)  # right size, wrong content
    assert "wrong hash: tokenizer.json" in model_store.problems(tmp_path)


class _FakeResponse(io.BytesIO):
    def __init__(self, data, status=200):
        super().__init__(data)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _serve(monkeypatch, payload: bytes):
    """Make urlopen return payload, honouring Range requests."""

    def fake_urlopen(req, timeout):
        rng = req.get_header("Range")
        if rng:
            start = int(rng.split("=")[1].rstrip("-"))
            return _FakeResponse(payload[start:], status=206)
        return _FakeResponse(payload)

    monkeypatch.setattr(model_store.urllib.request, "urlopen", fake_urlopen)


def test_download_resumes_a_partial_file_and_verifies_it(tmp_path, monkeypatch):
    payload = b"kokoro" * 1000
    f = RemoteFile("voices/test.bin", len(payload), hashlib.sha256(payload).hexdigest())
    dest = f.local_path(tmp_path)
    dest.parent.mkdir(parents=True)
    dest.with_name(dest.name + ".part").write_bytes(payload[:1234])
    _serve(monkeypatch, payload)

    model_store._download(f, dest)

    assert dest.read_bytes() == payload
    assert not dest.with_name(dest.name + ".part").exists()


def test_download_rejects_a_file_with_the_wrong_hash(tmp_path, monkeypatch):
    payload = b"tampered" * 100
    f = RemoteFile("voices/test.bin", len(payload), "0" * 64)
    dest = f.local_path(tmp_path)
    _serve(monkeypatch, payload)

    with pytest.raises(OSError, match="integrity check"):
        model_store._download(f, dest)
    assert not dest.exists()
