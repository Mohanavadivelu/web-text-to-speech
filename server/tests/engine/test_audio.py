import io

import numpy as np
import soundfile as sf

from server.engine import audio

SR = audio.SAMPLE_RATE


def _tone(seconds=2.0):
    t = np.arange(int(SR * seconds)) / SR
    return (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def test_pcm16_is_two_bytes_per_sample_and_clips():
    pcm = audio.to_pcm16(np.array([0.0, 1.0, -1.0, 2.0], dtype=np.float32))
    assert np.frombuffer(pcm, "<i2").tolist() == [0, 32767, -32767, 32767]


def test_wav_round_trip():
    x = _tone()
    y, sr = sf.read(io.BytesIO(audio.encode_wav(x)), dtype="float32")
    assert sr == SR
    np.testing.assert_allclose(y, x, atol=1e-4)


def test_mp3_is_about_64_kbps_and_decodes():
    x = _tone(10.0)
    data = audio.encode_mp3(x)
    kbps = len(data) * 8 / 10 / 1000
    assert 56 <= kbps <= 72
    y, sr = sf.read(io.BytesIO(data), dtype="float32")
    assert sr == SR
    assert abs(len(y) / sr - 10.0) < 0.2


def test_pitch_shift_changes_length_by_the_factor():
    x = _tone()
    factor = audio.pitch_factor(12)  # one octave up
    assert factor == 2.0
    assert len(audio.pitch_shift(x, factor)) == len(x) // 2
    assert audio.pitch_shift(x, 1.0) is x
