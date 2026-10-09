"""Audio helpers: pitch shifting and encoding (PCM16, WAV, MP3)."""

from __future__ import annotations

import io

import numpy as np
import soundfile as sf

SAMPLE_RATE = 24_000

# libsndfile's MP3 encoder takes a 0–1 compression level instead of a bitrate.
# At constant bitrate, 0.63 gives about 64 kbps for 24 kHz mono speech.
MP3_COMPRESSION_LEVEL = 0.63


def pitch_factor(semitones: float) -> float:
    return 2.0 ** (semitones / 12.0)


def pitch_shift(audio: np.ndarray, factor: float) -> np.ndarray:
    """Resample audio so it plays `factor` times higher (and shorter).

    The engine generates speech at speed / factor first, so the net effect is a
    pitch change with the original duration.
    """
    if factor == 1.0 or len(audio) < 2:
        return audio
    n_out = max(1, round(len(audio) / factor))
    src = np.linspace(0, len(audio) - 1, n_out, dtype=np.float64)
    return np.interp(src, np.arange(len(audio)), audio).astype(np.float32)


def to_pcm16(audio: np.ndarray) -> bytes:
    """float32 in [-1, 1] → little-endian 16-bit PCM bytes (for streaming)."""
    clipped = np.clip(audio, -1.0, 1.0)
    return (clipped * 32767.0).astype("<i2").tobytes()


def encode_wav(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, audio, sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def encode_mp3(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    sf.write(
        buf,
        audio,
        sample_rate,
        format="MP3",
        subtype="MPEG_LAYER_III",
        bitrate_mode="CONSTANT",
        compression_level=MP3_COMPRESSION_LEVEL,
    )
    return buf.getvalue()
