"""The engine catalogue, routing and Indic-Mio logic that doesn't need the model."""

import numpy as np
import pytest

from server import engines
from server.config import Settings
from server.engines.indic_mio import voices as indic_voices
from server.engines.indic_mio.synth import split_sentences, target_length


def test_catalog_codes_and_voice_ids_are_unique_across_engines():
    codes = [lang.code for lang in engines.catalog()]
    assert len(codes) == len(set(codes)) == 30
    kokoro_ids = {
        v.id for lang in engines.catalog() if lang.engine == "kokoro" for v in lang.voices
    }
    indic_ids = {v.id for v in indic_voices.VOICES}
    assert not kokoro_ids & indic_ids


@pytest.mark.parametrize(
    ("lang", "voice", "blend", "result"),
    [
        ("a", "af_heart", None, "kokoro"),
        ("ta", "in_ananya", "in_heart", "indic_mio"),
        ("hi", "in_vikram", None, "indic_mio"),
    ],
)
def test_validate_returns_the_engine(lang, voice, blend, result):
    assert engines.validate(lang, voice, blend) == result


@pytest.mark.parametrize(
    ("lang", "voice", "message"),
    [
        ("ta", "af_heart", "doesn't belong"),  # Kokoro voice, Indic language
        ("a", "in_ananya", "doesn't belong"),
        ("ta", "in_nobody", "Unknown voice"),
        ("xx", "af_heart", "Unknown language"),
    ],
)
def test_validate_rejects_mixing_engines(lang, voice, message):
    with pytest.raises(ValueError, match=message):
        engines.validate(lang, voice)


def test_queue_routing():
    cpu = Settings(_env_file=None)
    assert cpu.queue_for("kokoro", 100) == "tts:short"
    assert cpu.queue_for("kokoro", 5000) == "tts:long"
    assert cpu.queue_for("indic_mio", 100) == "tts:indic"
    gpu = Settings(_env_file=None, split_short_long=False)
    assert gpu.queue_for("kokoro", 5000) == "tts:kokoro"


def test_model_versions_differ_per_engine():
    assert engines.model_version("kokoro") != engines.model_version("indic_mio")


def test_create_engine_rejects_unknown_names():
    with pytest.raises(ValueError, match="Unknown engine"):
        engines.create_engine("espeak")


# ── Indic-Mio text handling ──────────────────────────────────────────────────
def test_emotion_tags_stay_with_their_sentence():
    assert split_sentences("मुझे यह फिल्म पसंद आई! <happy> फिर मिलेंगे।") == [
        "मुझे यह फिल्म पसंद आई! <happy>",
        "फिर मिलेंगे।",
    ]


def test_sentences_split_on_indian_punctuation_and_lines():
    assert split_sentences("पहला वाक्य। दूसरा वाक्य॥\nதமிழ் வரி.") == [
        "पहला वाक्य।",
        "दूसरा वाक्य॥",
        "தமிழ் வரி.",
    ]


def test_long_sentences_are_cut_at_clauses_or_words():
    sentence = ("एक बहुत लंबा वाक्य, " * 40).strip()
    pieces = split_sentences(sentence, max_chars=120)
    assert all(len(p) <= 120 for p in pieces)
    assert " ".join(pieces).split() == sentence.split()


def test_target_length_scales_with_speed_and_pitch():
    assert target_length(25, speed=1.0, pitch_factor=1.0) == 24_000  # 25 tokens = 1 s
    assert target_length(25, speed=2.0, pitch_factor=1.0) == 12_000
    assert target_length(25, speed=1.0, pitch_factor=2.0) == 48_000  # halved again by the resample


def test_indic_voice_mixing():
    mixed = indic_voices.voice_embedding("in_ananya", "in_heart", 0.5)
    expected = (
        indic_voices.load_embedding("in_ananya") + indic_voices.load_embedding("in_heart")
    ) / 2
    np.testing.assert_allclose(mixed, expected, rtol=1e-6)
    assert indic_voices.voice_embedding("in_ananya", None) is indic_voices.load_embedding(
        "in_ananya"
    )
