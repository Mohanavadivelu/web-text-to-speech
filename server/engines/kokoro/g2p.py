"""Text → phonemes (G2P), and packing phonemes into model-sized chunks.

English (US and UK) uses misaki, with espeak-ng as the fallback for unknown words.
The other languages use espeak-ng directly (bundled by espeakng-loader).
"""

from __future__ import annotations

import logging
import re
import threading

from server.engines.kokoro.voices import LANGUAGES

log = logging.getLogger(__name__)

MAX_PHONEMES = 510  # model limit per call
_SENTENCE = re.compile(r"(?<=[.!?।॥…])\s+")

_g2p_cache: dict[str, object] = {}
_g2p_lock = threading.Lock()


def get_g2p(lang: str):
    """G2P callable for a language, created once per process."""
    with _g2p_lock:
        if lang not in _g2p_cache:
            _g2p_cache[lang] = _create(lang)
        return _g2p_cache[lang]


def _create(lang: str):
    from misaki import espeak

    espeak_voice = LANGUAGES[lang].espeak
    if espeak_voice is not None:
        return espeak.EspeakG2P(language=espeak_voice)

    from misaki import en

    british = lang == "b"
    try:
        fallback = espeak.EspeakFallback(british=british)
    except Exception as exc:  # unknown words are then skipped instead of spelled by espeak
        log.warning("espeak fallback unavailable: %s", exc)
        fallback = None
    return en.G2P(trf=False, british=british, fallback=fallback, unk="")


def phoneme_chunks(text: str, lang: str) -> list[str]:
    """Phonemes for a segment, packed into chunks of up to MAX_PHONEMES.

    Packing to the full length matters: Kokoro's pacing depends on chunk length,
    so many short calls sound slower than a few long ones.
    """
    g2p = get_g2p(lang)
    english = LANGUAGES[lang].espeak is None
    pieces = _SENTENCE.split(text) if english else text.splitlines()
    chunks: list[str] = []
    cur = ""
    for piece in pieces:
        if not piece.strip():
            continue
        phonemes = (g2p(piece.strip())[0] or "").strip()
        for part in split_long(phonemes):
            if cur and len(cur) + 1 + len(part) > MAX_PHONEMES:
                chunks.append(cur)
                cur = part
            else:
                cur = f"{cur} {part}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def split_long(phonemes: str) -> list[str]:
    """Split a phoneme string longer than MAX_PHONEMES at word boundaries."""
    if len(phonemes) <= MAX_PHONEMES:
        return [phonemes] if phonemes else []
    out: list[str] = []
    cur = ""
    for word in phonemes.split(" "):
        while len(word) > MAX_PHONEMES:
            out.append(word[:MAX_PHONEMES])
            word = word[MAX_PHONEMES:]
        if cur and len(cur) + 1 + len(word) > MAX_PHONEMES:
            out.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return out + ([cur] if cur else [])
