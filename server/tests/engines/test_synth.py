"""Engine tests with the real model (marked slow; see conftest.py)."""

import io
import threading
import time

import numpy as np
import pytest
import soundfile as sf

from server.engines.kokoro import voices
from server.engines.kokoro.synth import SAMPLE_RATE, GenerationCancelled
from server.tests.engines import reference

pytestmark = pytest.mark.slow

LONG_TEXT = (
    "The history of speech synthesis goes back centuries, to mechanical devices that "
    "imitated the human vocal tract. In the twentieth century, electronic systems made "
    "it possible to generate intelligible speech from text. Neural networks changed that, "
    "and today small open models can produce natural speech on an ordinary processor. "
) * 4


def _reference(lang):
    clip, sr = sf.read(io.BytesIO(reference.clip_path(lang).read_bytes()), dtype="float32")
    assert sr == SAMPLE_RATE
    return clip


@pytest.mark.parametrize("lang", sorted(reference.REFERENCE_TEXTS))
def test_output_matches_reference_audio(engine, lang):
    result = engine.generate(reference.REFERENCE_TEXTS[lang], lang, voices.default_voice(lang).id)
    clip = _reference(lang)
    similarity = reference.spectral_similarity(result, clip)
    length_diff = reference.length_difference(result, clip)
    assert length_diff <= reference.MAX_LENGTH_DIFFERENCE, f"length differs by {length_diff:.1%}"
    assert similarity >= reference.MIN_SIMILARITY, f"similarity {similarity:.4f}"


def test_reference_check_catches_a_changed_voice(engine):
    faster = engine.generate(reference.REFERENCE_TEXTS["a"], "a", "af_heart", speed=1.1)
    other_voice = engine.generate(reference.REFERENCE_TEXTS["a"], "a", "am_michael")
    assert not reference.matches(faster, _reference("a"))
    assert not reference.matches(other_voice, _reference("a"))


def test_chunks_and_progress_are_reported_and_add_up(engine):
    chunks, progress = [], []
    result = engine.generate(
        LONG_TEXT, "a", "af_heart", on_chunk=chunks.append, on_progress=progress.append
    )
    assert len(chunks) >= 2
    np.testing.assert_array_equal(np.concatenate(chunks), result)
    assert progress == sorted(progress)
    assert progress[-1] == 100


def test_short_first_segment_starts_streaming_sooner(engine):
    def first_chunk_seconds(first_segment_chars):
        started, first = time.perf_counter(), []
        engine.generate(
            LONG_TEXT, "a", "af_heart",
            first_segment_chars=first_segment_chars,
            on_chunk=lambda _c: first or first.append(time.perf_counter() - started),
        )  # fmt: skip
        return first[0]

    assert first_chunk_seconds(150) < first_chunk_seconds(None) / 2


def test_cancel_stops_quickly(engine):
    cancel = threading.Event()
    threading.Timer(0.5, cancel.set).start()
    started = time.perf_counter()
    with pytest.raises(GenerationCancelled):
        engine.generate(LONG_TEXT * 3, "a", "af_heart", cancel_event=cancel)
    assert time.perf_counter() - started < 0.5 + 1.0


def test_pitch_keeps_the_duration(engine):
    sentence = reference.REFERENCE_TEXTS["a"]
    normal = engine.generate(sentence, "a", "af_heart")
    higher = engine.generate(sentence, "a", "af_heart", pitch=4)
    assert abs(len(higher) - len(normal)) / len(normal) < 0.1
    assert not reference.matches(higher, normal)


def test_pronunciations_change_the_audio(engine):
    plain = engine.generate("I use Kokoro daily.", "a", "af_heart")
    custom = engine.generate(
        "I use Kokoro daily.", "a", "af_heart",
        pronunciations=[{"word": "Kokoro", "say": "cocoa row"}],
    )  # fmt: skip
    assert not np.array_equal(plain, custom)


def test_blended_voice_differs_from_both_voices(engine):
    sentence = "Mixing voices makes a new one."
    a = engine.generate(sentence, "a", "af_heart")
    b = engine.generate(sentence, "a", "af_bella")
    mixed = engine.generate(sentence, "a", "af_heart", blend_voice="af_bella", blend_ratio=0.5)
    assert not np.array_equal(mixed, a)
    assert not np.array_equal(mixed, b)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"source_text": "  "}, "no text"),
        ({"voice": "bf_emma"}, "doesn't belong"),
        ({"speed": 3.0}, "speed must be between"),
        ({"pitch": -7}, "pitch must be between"),
        ({"blend_ratio": 1.5}, "blend_ratio must be between"),
    ],
)
def test_invalid_input_is_rejected(engine, kwargs, message):
    args = {"source_text": "Hello.", "lang": "a", "voice": "af_heart"} | kwargs
    with pytest.raises(ValueError, match=message):
        engine.generate(**args)
