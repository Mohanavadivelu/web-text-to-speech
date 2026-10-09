"""What every speech engine provides, so the API and workers never depend on one model.

Each engine lives in its own package (server/engines/<name>/) with its own model
files, voices and dependencies. Model-independent helpers (audio encoding, text
cleanup, document extraction) live in server/engines/common/.

All engines produce 24 kHz mono float32 audio, so streaming, the player and
encoding are the same whichever engine made the audio.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

SAMPLE_RATE = 24_000
SPEED_RANGE = (0.5, 2.0)
PITCH_RANGE = (-6.0, 6.0)
BLEND_RANGE = (0.0, 1.0)


class GenerationCancelled(Exception):
    """Raised by generate() when its cancel_event is set."""


@dataclass(frozen=True)
class Voice:
    id: str  # unique across all engines
    name: str
    gender: str  # "female" or "male"
    grade: str | None = None
    tags: tuple[str, ...] = ()  # e.g. ("native",)


@dataclass(frozen=True)
class Language:
    code: str  # unique across all engines
    name: str
    engine: str
    preview_text: str
    voices: tuple[Voice, ...] = field(default_factory=tuple)
    emotions: tuple[str, ...] = ()  # tags the engine understands, e.g. "happy"

    @property
    def default_voice(self) -> Voice:
        return self.voices[0]


class Engine(Protocol):
    """A loaded speech model that a worker runs jobs on."""

    name: str
    realtime_factor: float | None

    def load(self, warm_up: bool = True) -> None: ...

    def estimate_generation_seconds(self, audio_seconds: float) -> float: ...

    def generate(
        self,
        source_text: str,
        lang: str,
        voice: str,
        speed: float = 1.0,
        pitch: float = 0.0,
        blend_voice: str | None = None,
        blend_ratio: float = 0.5,
        pronunciations: list[dict] | None = None,
        first_segment_chars: int | None = None,
        on_chunk: Callable[[np.ndarray], None] | None = None,
        on_progress: Callable[[int], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> np.ndarray: ...


def check_range(name: str, value: float, bounds: tuple[float, float]) -> None:
    low, high = bounds
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low:g} and {high:g}.")
