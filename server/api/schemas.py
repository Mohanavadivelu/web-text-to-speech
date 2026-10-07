"""Request and response models (these also define the OpenAPI schema the frontend uses)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from server.engine import voices
from server.engine.synth import BLEND_RANGE, PITCH_RANGE, SPEED_RANGE


class ErrorBody(BaseModel):
    code: Literal[
        "invalid_input",
        "too_long",
        "quota_exceeded",
        "rate_limited",
        "busy",
        "not_found",
        "internal",
    ]
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


# ── Voices ───────────────────────────────────────────────────────────────────
class VoiceOut(BaseModel):
    id: str
    name: str
    gender: Literal["female", "male"]
    grade: str | None


class LanguageOut(BaseModel):
    code: str
    name: str
    default_voice: str
    preview_text: str
    voices: list[VoiceOut]


class VoicesResponse(BaseModel):
    languages: list[LanguageOut]
    speed: tuple[float, float] = SPEED_RANGE
    pitch: tuple[float, float] = PITCH_RANGE


# ── Jobs ─────────────────────────────────────────────────────────────────────
class Pronunciation(BaseModel):
    word: str = Field(min_length=1, max_length=100)
    say: str = Field(min_length=1, max_length=200)


class JobCreate(BaseModel):
    text: str = Field(min_length=1, description="Text to speak (limit depends on the account)")
    lang: str = Field("a", description="Language code, see /v1/voices")
    voice: str = "af_heart"
    blend_voice: str | None = None
    blend_ratio: float = Field(0.5, ge=BLEND_RANGE[0], le=BLEND_RANGE[1])
    speed: float = Field(1.0, ge=SPEED_RANGE[0], le=SPEED_RANGE[1])
    pitch: float = Field(0.0, ge=PITCH_RANGE[0], le=PITCH_RANGE[1])
    pronunciations: list[Pronunciation] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def _check_voice(self) -> JobCreate:
        if not self.text.strip():
            raise ValueError("There is no text to speak.")
        voices.validate(self.lang, self.voice, self.blend_voice)  # ValueError → 422
        return self


class JobOut(BaseModel):
    id: str
    status: Literal["queued", "running", "done", "error", "cancelled"]
    progress: int = 0
    queue_position: int | None = None
    estimated_seconds: float | None = None
    audio_seconds: float | None = None
    url: str | None = Field(None, description="Signed MP3 link, valid for an hour (when done)")
    error: str | None = None
    stream_url: str


# ── Text ─────────────────────────────────────────────────────────────────────
class TextIn(BaseModel):
    text: str = Field(max_length=2_000_000)


class TextOut(BaseModel):
    text: str


class ExtractOut(BaseModel):
    text: str
    cleaned: bool
    characters: int


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    redis: Literal["ok", "down"]
    workers: int
