"""IndicMioEngine: text → 24 kHz speech with Indic-Mio (22 Indian languages + English).

Indic-Mio is a small language model (Qwen3-0.6B fine-tune) that writes speech as
codec tokens, 25 per second of audio; MioCodec turns them into a waveform in the
chosen voice. Text is spoken one sentence at a time, so audio streams out sentence
by sentence.

Speed: on a GPU, decoding is compiled with a static key/value cache (CUDA graphs),
about 2× faster than real time on a 4 GB RTX 3050 Ti; the first compile happens in
load(). On a CPU it works but is slower than real time.

    python -m server.engines.indic_mio.synth "नमस्ते!" --lang hi --out hello.wav
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from server.engines.base import (
    BLEND_RANGE,
    PITCH_RANGE,
    SAMPLE_RATE,
    SPEED_RANGE,
    GenerationCancelled,
    check_range,
)
from server.engines.common import audio, text
from server.engines.indic_mio import model_store, voices

log = logging.getLogger(__name__)

SPEECH_TOKEN_OFFSET = 151_669  # first speech token id in the vocabulary
SPEECH_VOCAB = 12_800
TOKENS_PER_SECOND = 25
SAMPLES_PER_TOKEN = SAMPLE_RATE // TOKENS_PER_SECOND  # 960
MAX_SENTENCE_CHARS = 280  # the reference server accepts 300 characters per call
MAX_NEW_TOKENS = 700  # 28 s of audio per sentence
# Prompt + speech tokens. One fixed size: the static cache is rebuilt (and the decoder
# recompiled) whenever a call needs a bigger one, so it never has to grow
MAX_LENGTH = 1280
TEMPERATURE = 0.8

_SENTENCE_END = re.compile(r"(?<=[.!?।॥…|?])\s+")
_CLAUSE_END = re.compile(r"(?<=[,;:—،])\s+")
_LEADING_TAGS = re.compile(r"^((?:<[a-z]+>\s*)+)")


def split_sentences(source: str, max_chars: int = MAX_SENTENCE_CHARS) -> list[str]:
    """Sentences of at most max_chars, keeping emotion tags with the sentence they end.

    Tags like <happy> go at the end of a sentence; splitting after "!" would otherwise
    move "<happy>" to the start of the next sentence.
    """
    pieces: list[str] = []
    for paragraph in re.split(r"\n\s*\n|\n", source):
        for sentence in _SENTENCE_END.split(paragraph.strip()):
            sentence = sentence.strip()
            if not sentence:
                continue
            tags = _LEADING_TAGS.match(sentence)
            if tags and pieces:
                pieces[-1] = f"{pieces[-1]} {tags.group(1).strip()}"
                sentence = sentence[tags.end() :].strip()
                if not sentence:
                    continue
            pieces.extend(_split_long(sentence, max_chars))
    return pieces


def _split_long(sentence: str, max_chars: int) -> list[str]:
    if len(sentence) <= max_chars:
        return [sentence]
    out, cur = [], ""
    for part in _CLAUSE_END.split(sentence):
        words = part.split() if len(part) > max_chars else [part]
        for word in words:
            if cur and len(cur) + 1 + len(word) > max_chars:
                out.append(cur)
                cur = word
            else:
                cur = f"{cur} {word}".strip()
    return out + ([cur] if cur else [])


def target_length(n_tokens: int, speed: float, pitch_factor: float) -> int:
    """Samples to decode so that, after the pitch resample, the audio lasts 1/speed as long."""
    return max(1, round(n_tokens * SAMPLES_PER_TOKEN / speed * pitch_factor))


class IndicMioEngine:
    name = voices.ENGINE
    default_realtime_factor = 1.8

    def __init__(self, device: str | None = None, compile_decoding: bool | None = None):
        self.device = (device or os.environ.get("ENGINE_DEVICE") or "cuda").lower()
        if compile_decoding is None:
            compile_decoding = os.environ.get("INDIC_COMPILE", "1") == "1"
        self.compile_decoding = compile_decoding
        self.realtime_factor: float | None = None
        self._lock = threading.Lock()
        self._loaded = False

    # ── model ────────────────────────────────────────────────────────────────
    def load(self, warm_up: bool = True) -> None:
        with self._lock:
            if not self._loaded:
                self._load()
        if warm_up:
            started = time.perf_counter()
            # Compiling happens on the first calls; do it now, not on a user's job
            for sentence in ("नमस्ते, आप कैसे हैं?", "Ready.", "வணக்கம்! இன்று நல்ல நாள்."):
                self.generate(sentence, "hi", voices.VOICES[0].id)
            log.info("Indic-Mio warmed up in %.0fs", time.perf_counter() - started)

    def _load(self) -> None:
        import torch
        from miocodec import MioCodecModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if self.device == "cuda" and not torch.cuda.is_available():
            log.warning("CUDA requested but not available; Indic-Mio runs on the CPU (slow)")
            self.device = "cpu"
        self._torch = torch
        dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
        lm_dir = model_store.repo_dir(model_store.LM)
        codec_dir = model_store.repo_dir(model_store.CODEC)
        log.info("Loading Indic-Mio on %s", self.device)
        self._tokenizer = AutoTokenizer.from_pretrained(lm_dir)
        self._lm = AutoModelForCausalLM.from_pretrained(lm_dir, dtype=dtype).to(self.device).eval()
        self._codec = (
            MioCodecModel.from_pretrained(
                config_path=str(codec_dir / "config.yaml"),
                weights_path=str(codec_dir / "model.safetensors"),
            )
            .eval()
            .to(self.device)
        )
        self._use_static = self.device == "cuda" and self.compile_decoding
        if self._use_static:
            from transformers.generation.configuration_utils import CompileConfig

            self._compile_config = CompileConfig(fullgraph=False, mode="reduce-overhead")
        self._loaded = True

    def estimate_generation_seconds(self, audio_seconds: float) -> float:
        return audio_seconds / (self.realtime_factor or self.default_realtime_factor)

    # ── generation ───────────────────────────────────────────────────────────
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
        first_segment_chars: int | None = None,  # sentences are already short
        on_chunk: Callable[[np.ndarray], None] | None = None,
        on_progress: Callable[[int], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> np.ndarray:
        voices.validate(lang, voice, blend_voice)
        check_range("speed", speed, SPEED_RANGE)
        check_range("pitch", pitch, PITCH_RANGE)
        check_range("blend_ratio", blend_ratio, BLEND_RANGE)
        if not source_text.strip():
            raise ValueError("There is no text to speak.")
        with self._lock:
            if not self._loaded:
                self._load()

        started = time.perf_counter()
        prepared = text.apply_pronunciations(source_text, pronunciations or [], lang)
        sentences = split_sentences(prepared)
        embedding = voices.voice_embedding(voice, blend_voice, blend_ratio)
        factor = audio.pitch_factor(pitch)
        log.info(
            "Generating %d sentence(s), %d chars, voice=%s blend=%s@%.2f speed=%s pitch=%+.1f",
            len(sentences), len(source_text), voice, blend_voice, blend_ratio, speed, pitch,
        )  # fmt: skip

        parts: list[np.ndarray] = []
        for i, sentence in enumerate(sentences):
            if cancel_event is not None and cancel_event.is_set():
                raise GenerationCancelled()
            with self._lock:
                tokens = self._speech_tokens(sentence, cancel_event)
                if not tokens:
                    log.warning("No speech tokens for a sentence of %d chars", len(sentence))
                    continue
                wav = self._decode(tokens, embedding, target_length(len(tokens), speed, factor))
            wav = audio.pitch_shift(wav, factor)
            parts.append(wav)
            if on_chunk:
                on_chunk(wav)
            if on_progress:
                on_progress(min(99, int((i + 1) / len(sentences) * 100)))

        if not parts:
            raise ValueError("The engine produced no audio for this text.")
        full = np.concatenate(parts) if len(parts) > 1 else parts[0]
        seconds, elapsed = len(full) / SAMPLE_RATE, time.perf_counter() - started
        if elapsed > 0.5 and seconds > 1.0:
            rtf = seconds / elapsed
            self.realtime_factor = (
                rtf if self.realtime_factor is None else 0.7 * self.realtime_factor + 0.3 * rtf
            )
        if on_progress:
            on_progress(100)
        log.info("%.2fs of audio in %.2fs (%.1fx real time)", seconds, elapsed, seconds / elapsed)
        return full

    def _speech_tokens(self, sentence: str, cancel_event: threading.Event | None) -> list[int]:
        torch = self._torch
        from transformers import StoppingCriteria, StoppingCriteriaList

        class Stop(StoppingCriteria):
            """On cancel, or at MAX_NEW_TOKENS (the length limit below is set for the cache)."""

            def __call__(self, input_ids, scores, **kwargs):
                if cancel_event is not None and cancel_event.is_set():
                    return True
                return input_ids.shape[1] - prompt_tokens >= MAX_NEW_TOKENS

        prompt = self._tokenizer.apply_chat_template(
            [{"role": "user", "content": sentence}], tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self.device)
        # The length limit is the same for every sentence: the model stops itself with its
        # end-of-speech token, and a constant limit keeps the static cache and the compiled
        # code the same size (a varying one makes it recompile, ~10x slower)
        prompt_tokens = inputs["input_ids"].shape[1]
        if prompt_tokens + MAX_NEW_TOKENS > MAX_LENGTH:
            log.warning("Long prompt (%d tokens) leaves less room for speech", prompt_tokens)
        options: dict = dict(
            # (the model's generation_config sets max_new_tokens, which wins over max_length)
            max_new_tokens=(
                max(MAX_LENGTH - prompt_tokens, 1) if self._use_static else MAX_NEW_TOKENS
            ),
            do_sample=True,
            temperature=TEMPERATURE,
            top_p=1.0,
            pad_token_id=self._tokenizer.pad_token_id,
            stopping_criteria=StoppingCriteriaList([Stop()]),
        )
        if self._use_static:
            # Transformers keeps one static cache and reuses it across calls
            options["cache_implementation"] = "static"
            options["compile_config"] = self._compile_config
        with torch.inference_mode():
            output = self._lm.generate(**inputs, **options)
        if cancel_event is not None and cancel_event.is_set():
            raise GenerationCancelled()
        generated = output[0][inputs["input_ids"].shape[1] :].tolist()
        return [
            t - SPEECH_TOKEN_OFFSET
            for t in generated
            if SPEECH_TOKEN_OFFSET <= t < SPEECH_TOKEN_OFFSET + SPEECH_VOCAB
        ]

    def _decode(self, tokens: list[int], embedding: np.ndarray, length: int) -> np.ndarray:
        torch = self._torch
        with torch.inference_mode():
            wav = self._codec.decode(
                global_embedding=torch.from_numpy(np.array(embedding)).to(self.device),
                content_token_indices=torch.tensor(tokens, dtype=torch.long, device=self.device),
                target_audio_length=length,
            )
        return wav.float().squeeze().cpu().numpy().astype(np.float32)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Speak text with Indic-Mio.")
    parser.add_argument("text")
    parser.add_argument("--lang", default="hi")
    parser.add_argument("--voice", default=voices.VOICES[0].id)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--pitch", type=float, default=0.0)
    parser.add_argument("--out", type=Path, default=Path("speech.wav"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    engine = IndicMioEngine()
    engine.load(warm_up=False)
    result = engine.generate(args.text, args.lang, args.voice, args.speed, args.pitch)
    encode = audio.encode_mp3 if args.out.suffix.lower() == ".mp3" else audio.encode_wav
    args.out.write_bytes(encode(result))
    log.info("Wrote %s (%.1fs)", args.out, len(result) / SAMPLE_RATE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
