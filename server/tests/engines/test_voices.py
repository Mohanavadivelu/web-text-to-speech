import numpy as np
import pytest

from server.engines.kokoro import model_store, voices


def test_seven_languages_and_37_voices():
    assert len(voices.LANGUAGES) == 7
    assert len(voices.VOICES) == 37


def test_every_voice_belongs_to_a_known_language_and_has_a_model_file():
    for voice in voices.VOICES.values():
        assert voice.lang in voices.LANGUAGES
        assert voice.id[0] == voice.lang  # Kokoro's naming: first letter is the language
        assert model_store.voice_path(voice.id).name == f"{voice.id}.bin"


def test_every_language_has_a_default_voice_of_its_own():
    for code in voices.LANGUAGES:
        assert voices.default_voice(code).lang == code


def test_gender_from_voice_id():
    assert voices.VOICES["af_heart"].gender == "female"
    assert voices.VOICES["am_adam"].gender == "male"


@pytest.mark.parametrize(
    ("lang", "voice", "blend", "message"),
    [
        ("x", "af_heart", None, "Unknown language"),
        ("a", "nobody", None, "Unknown voice"),
        ("a", "bf_emma", None, "doesn't belong"),
        ("a", "af_heart", "hf_alpha", "doesn't belong"),
    ],
)
def test_validate_rejects_bad_combinations(lang, voice, blend, message):
    with pytest.raises(ValueError, match=message):
        voices.validate(lang, voice, blend)


def test_validate_accepts_good_combination():
    voices.validate("a", "af_heart", "af_bella")


@pytest.mark.slow
def test_style_tables_have_the_model_shape():
    table = voices.load_style("af_heart")
    assert table.shape == (voices.STYLE_ROWS, voices.STYLE_DIM)
    assert table.dtype == np.float32


@pytest.mark.slow
def test_blending_at_zero_is_the_base_voice_and_halfway_is_the_mean():
    base, other = voices.load_style("af_heart"), voices.load_style("af_bella")
    assert voices.voice_style("af_heart", "af_bella", 0.0) is base
    np.testing.assert_allclose(
        voices.voice_style("af_heart", "af_bella", 0.5), (base + other) / 2, rtol=1e-6
    )
