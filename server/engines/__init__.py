"""Speech engines, one package each (kokoro/, indic_mio/), behind one catalogue.

The catalogue and validation only import the lightweight voices modules, so the API
never loads PyTorch or ONNX Runtime. A worker creates the one engine it runs with
create_engine(); that's where the heavy imports happen.
"""

from __future__ import annotations

from functools import lru_cache

ENGINES = ("kokoro", "indic_mio")


@lru_cache(maxsize=1)
def catalog():
    """All languages of all engines (server.engines.base.Language), Kokoro first."""
    from server.engines.indic_mio import voices as indic_voices
    from server.engines.kokoro import voices as kokoro_voices

    return tuple(kokoro_voices.catalog()) + tuple(indic_voices.catalog())


def language(code: str):
    for lang in catalog():
        if lang.code == code:
            return lang
    raise ValueError(f"Unknown language '{code}'.")


def engine_for(lang_code: str) -> str:
    return language(lang_code).engine


def validate(lang_code: str, voice_id: str, blend_voice: str | None = None) -> str:
    """Check the language/voice combination; returns the engine that will speak it."""
    lang = language(lang_code)
    ids = {v.id for v in lang.voices}
    for vid in filter(None, (voice_id, blend_voice)):
        if vid not in ids:
            if any(vid in {v.id for v in other.voices} for other in catalog()):
                raise ValueError(f"Voice '{vid}' doesn't belong to {lang.name}.")
            raise ValueError(f"Unknown voice '{vid}'.")
    return lang.engine


def model_version(name: str) -> str:
    """The pinned model revision of an engine (part of the result cache key)."""
    if name == "kokoro":
        from server.engines.kokoro import model_store

        return f"kokoro@{model_store.REVISION}"
    if name == "indic_mio":
        from server.engines.indic_mio import model_store

        return f"indic_mio@{model_store.LM.revision}+{model_store.CODEC.revision}"
    raise ValueError(f"Unknown engine '{name}'.")


def create_engine(name: str, **kwargs):
    """The engine a worker runs (imports its heavy dependencies only here)."""
    if name == "kokoro":
        from server.engines.kokoro.synth import KokoroEngine

        return KokoroEngine(**kwargs)
    if name == "indic_mio":
        from server.engines.indic_mio.synth import IndicMioEngine

        return IndicMioEngine(**kwargs)
    raise ValueError(f"Unknown engine '{name}'. Known: {', '.join(ENGINES)}")
