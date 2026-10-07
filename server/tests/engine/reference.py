"""Reference audio: fixed sentences, where the clips live, and how audio is compared.

The clips in server/tests/reference/ are made with scripts/make_reference_audio.py
on Linux (python:3.12-slim, like production). Regenerate them only when a change
to the voice is intended, and listen to the new clips before committing them.
"""

from pathlib import Path

import numpy as np

REFERENCE_DIR = Path(__file__).resolve().parents[1] / "reference"
MIN_SIMILARITY = 0.997
MAX_LENGTH_DIFFERENCE = 0.02  # 2%

# One sentence per language, with the language's default voice
REFERENCE_TEXTS = {
    "a": "The quick brown fox jumps over the lazy dog, then naps in the warm afternoon sun.",
    "b": "Shall we have a cup of tea before the train leaves the station at half past four?",
    "h": "आज मौसम बहुत सुहाना है, चलो पार्क में टहलने चलते हैं।",
    "f": "Le petit chat dort tranquillement sur le canapé du salon.",
    "i": "Domani andremo al mare con tutta la famiglia, se non piove.",
    "e": "Mañana vamos a la playa con toda la familia, si no llueve.",
    "p": "Amanhã vamos à praia com toda a família, se não chover.",
}


def clip_path(lang: str) -> Path:
    return REFERENCE_DIR / f"{lang}.wav"


def _log_spectrogram(x: np.ndarray, n_fft: int = 1024, hop: int = 256) -> np.ndarray:
    window = np.hanning(n_fft).astype(np.float32)
    frames = np.lib.stride_tricks.sliding_window_view(x, n_fft)[::hop] * window
    return np.log1p(np.abs(np.fft.rfft(frames, axis=1)))


def spectral_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Correlation of log-magnitude spectrograms over the common length (1.0 = identical)."""
    n = min(len(a), len(b))
    sa, sb = _log_spectrogram(a[:n]), _log_spectrogram(b[:n])
    return float(np.corrcoef(sa.ravel(), sb.ravel())[0, 1])


def length_difference(a: np.ndarray, b: np.ndarray) -> float:
    return abs(len(a) - len(b)) / max(len(b), 1)


def matches(audio: np.ndarray, reference: np.ndarray) -> bool:
    return (
        length_difference(audio, reference) <= MAX_LENGTH_DIFFERENCE
        and spectral_similarity(audio, reference) >= MIN_SIMILARITY
    )
