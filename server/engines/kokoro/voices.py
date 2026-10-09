"""Languages and voices of Kokoro-82M v1.0, and their style tables.

Grades are the overall quality grades from the model card. Gender comes from the
second letter of the voice id (f = female, m = male).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from server.engines import base

STYLE_ROWS = 510  # one style row per phoneme count (1–510)
STYLE_DIM = 256


@dataclass(frozen=True)
class Language:
    code: str  # Kokoro language code, used everywhere in the API
    name: str
    espeak: str | None  # espeak-ng voice for G2P; None = misaki English
    preview_text: str


@dataclass(frozen=True)
class Voice:
    id: str
    name: str
    lang: str
    grade: str | None

    @property
    def gender(self) -> str:
        return "female" if self.id[1] == "f" else "male"


LANGUAGES: dict[str, Language] = {
    lang.code: lang
    for lang in (
        Language("a", "American English", None, "Hi there! This is how my voice sounds."),
        Language("b", "British English", None, "Hello there! This is how my voice sounds."),
        Language("h", "Hindi", "hi", "नमस्ते! मेरी आवाज़ ऐसी सुनाई देती है।"),
        Language("f", "French", "fr-fr", "Bonjour ! Voici à quoi ressemble ma voix."),
        Language("i", "Italian", "it", "Ciao! Ecco come suona la mia voce."),
        Language("e", "Spanish", "es", "¡Hola! Así es como suena mi voz."),
        Language("p", "Brazilian Portuguese", "pt-br", "Olá! É assim que a minha voz soa."),
    )
}

# (voice id, display name, grade). The first voice of each language is its default.
_VOICE_DATA: dict[str, list[tuple[str, str, str | None]]] = {
    "a": [
        ("af_heart", "Heart", "A"),
        ("af_bella", "Bella", "A-"),
        ("af_nicole", "Nicole", "B-"),
        ("af_aoede", "Aoede", "C+"),
        ("af_kore", "Kore", "C+"),
        ("af_sarah", "Sarah", "C+"),
        ("af_alloy", "Alloy", "C"),
        ("af_nova", "Nova", "C"),
        ("af_sky", "Sky", "C-"),
        ("am_fenrir", "Fenrir", "C+"),
        ("am_michael", "Michael", "C+"),
        ("am_puck", "Puck", "C+"),
        ("am_echo", "Echo", "D"),
        ("am_eric", "Eric", "D"),
        ("am_liam", "Liam", "D"),
        ("am_adam", "Adam", "F+"),
    ],
    "b": [
        ("bf_emma", "Emma", "B-"),
        ("bf_isabella", "Isabella", "C"),
        ("bf_alice", "Alice", "D"),
        ("bf_lily", "Lily", "D"),
        ("bm_fable", "Fable", "C"),
        ("bm_george", "George", "C"),
        ("bm_lewis", "Lewis", "D+"),
        ("bm_daniel", "Daniel", "D"),
    ],
    "h": [
        ("hf_alpha", "Alpha", "C"),
        ("hf_beta", "Beta", "C"),
        ("hm_omega", "Omega", "C"),
        ("hm_psi", "Psi", "C"),
    ],
    "f": [("ff_siwis", "Siwis", "B-")],
    "i": [("if_sara", "Sara", "C"), ("im_nicola", "Nicola", "C")],
    "e": [("ef_dora", "Dora", None), ("em_alex", "Alex", None), ("em_santa", "Santa", None)],
    "p": [("pf_dora", "Dora", None), ("pm_alex", "Alex", None), ("pm_santa", "Santa", None)],
}

VOICES: dict[str, Voice] = {
    vid: Voice(vid, name, lang, grade)
    for lang, entries in _VOICE_DATA.items()
    for vid, name, grade in entries
}


def catalog() -> list[base.Language]:
    """Kokoro's languages and voices in the shared catalogue format."""
    return [
        base.Language(
            code=lang.code,
            name=lang.name,
            engine="kokoro",
            preview_text=lang.preview_text,
            voices=tuple(
                base.Voice(id=v.id, name=v.name, gender=v.gender, grade=v.grade)
                for v in voices_for(lang.code)
            ),
        )
        for lang in LANGUAGES.values()
    ]


def voices_for(lang: str) -> list[Voice]:
    return [v for v in VOICES.values() if v.lang == lang]


def default_voice(lang: str) -> Voice:
    return voices_for(lang)[0]


def validate(lang: str, voice_id: str, blend_voice: str | None = None) -> None:
    """Raise ValueError with a readable message if the combination isn't valid."""
    if lang not in LANGUAGES:
        raise ValueError(f"Unknown language '{lang}'.")
    for vid in filter(None, (voice_id, blend_voice)):
        voice = VOICES.get(vid)
        if voice is None:
            raise ValueError(f"Unknown voice '{vid}'.")
        if voice.lang != lang:
            raise ValueError(f"Voice '{vid}' doesn't belong to {LANGUAGES[lang].name}.")


@lru_cache(maxsize=64)
def load_style(voice_id: str) -> np.ndarray:
    """Style table of a voice, shape (510, 256) float32, read-only."""
    from server.engines.kokoro import model_store

    table = np.fromfile(model_store.voice_path(voice_id), dtype=np.float32)
    table = table.reshape(STYLE_ROWS, STYLE_DIM)
    table.flags.writeable = False
    return table


def voice_style(voice_id: str, blend_voice: str | None = None, blend_ratio: float = 0.5):
    """Style table for a voice, optionally mixed with a second voice.

    blend_ratio is the share of the second voice (0.0–1.0).
    """
    base = load_style(voice_id)
    if not blend_voice or blend_voice == voice_id or blend_ratio <= 0:
        return base
    ratio = min(1.0, float(blend_ratio))
    return ((1.0 - ratio) * base + ratio * load_style(blend_voice)).astype(np.float32)
