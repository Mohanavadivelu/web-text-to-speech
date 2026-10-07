"""KokoroEngine: text → 24 kHz mono float32 speech with Kokoro-82M on ONNX Runtime (CPU).

One engine per worker process: the model is loaded once and kept in memory.
generate() is thread-safe (calls are serialised) and supports streaming callbacks
and fast cancel.

Command line, for quick experiments:

    python -m server.engine.synth "Hello there." --voice af_heart --out hello.wav
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from server.engine import audio, g2p, model_store, text, voices

log = logging.getLogger(__name__)

SAMPLE_RATE = audio.SAMPLE_RATE
SPEED_RANGE = (0.5, 2.0)
PITCH_RANGE = (-6.0, 6.0)
BLEND_RANGE = (0.0, 1.0)


class GenerationCancelled(Exception):
    """Raised by generate() when its cancel_event is set."""


class KokoroEngine:
    default_realtime_factor = 3.0

    def __init__(self, threads: int | None = None):
        if threads is None:
            threads = int(os.environ.get("ENGINE_THREADS", "0") or 0)
        self.threads = threads  # ONNX Runtime intra-op threads; 0 = runtime default
        self.spin = os.environ.get("ENGINE_SPIN", "1") == "1"
        self.realtime_factor: float | None = None  # measured audio-seconds per second
        self._session = None
        self._lock = threading.Lock()

    # ── model ────────────────────────────────────────────────────────────────
    def load(self, warm_up: bool = True) -> None:
        """Load the model now instead of on the first generate() call.

        With warm_up, also prepare every language's G2P (spaCy and misaki take
        several seconds the first time) and run one short generation, so the first
        real request is as fast as the rest.
        """
        with self._lock:
            self._ensure_session()
        if warm_up:
            started = time.perf_counter()
            for lang in voices.LANGUAGES:
                g2p.get_g2p(lang)
            self.generate("Ready.", "a", voices.default_voice("a").id)
            log.info("Engine warmed up in %.1fs", time.perf_counter() - started)

    def _ensure_session(self):
        if self._session is None:
            import onnxruntime as ort

            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            opts.intra_op_num_threads = self.threads
            opts.inter_op_num_threads = 1
            if not self.spin:
                # Idle threads sleep instead of busy-waiting: slightly slower alone, but
                # several workers on one machine stop burning CPU fighting each other
                opts.add_session_config_entry("session.intra_op.allow_spinning", "0")
            path = model_store.model_path()
            log.info("Loading %s (%s threads)", path, self.threads or "auto")
            self._session = ort.InferenceSession(
                str(path), opts, providers=["CPUExecutionProvider"]
            )
        return self._session

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
        first_segment_chars: int | None = None,
        on_chunk: Callable[[np.ndarray], None] | None = None,
        on_progress: Callable[[int], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> np.ndarray:
        """Synthesise speech; returns float32 audio at SAMPLE_RATE.

        on_chunk(audio) is called with each segment's audio as soon as it is ready,
        on_progress(percent) after each segment. Raises ValueError for invalid
        input, GenerationCancelled when cancel_event is set.
        """
        voices.validate(lang, voice, blend_voice)
        _check_range("speed", speed, SPEED_RANGE)
        _check_range("pitch", pitch, PITCH_RANGE)
        _check_range("blend_ratio", blend_ratio, BLEND_RANGE)
        if not source_text.strip():
            raise ValueError("There is no text to speak.")

        def check_cancel():
            if cancel_event is not None and cancel_event.is_set():
                raise GenerationCancelled()

        started = time.perf_counter()
        style = voices.voice_style(voice, blend_voice, blend_ratio)
        factor = audio.pitch_factor(pitch)
        prepared = text.apply_pronunciations(source_text, pronunciations or [], lang)
        segments = text.split_segments(prepared, first_segment_chars=first_segment_chars)
        if voices.LANGUAGES[lang].espeak is not None:
            segments = [text.break_lines(s) for s in segments]
        log.info(
            "Generating %d segment(s), %d chars, voice=%s blend=%s@%.2f speed=%s pitch=%+.1f",
            len(segments), len(source_text), voice, blend_voice, blend_ratio, speed, pitch,
        )  # fmt: skip

        parts: list[np.ndarray] = []
        for i, segment in enumerate(segments):
            check_cancel()
            seg_audio = self._synth_segment(segment, lang, style, speed / factor, cancel_event)
            seg_audio = audio.pitch_shift(seg_audio, factor)
            if len(seg_audio):
                parts.append(seg_audio)
                if on_chunk:
                    on_chunk(seg_audio)
            if on_progress:
                on_progress(min(99, int((i + 1) / len(segments) * 100)))

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
        log.info(
            "%.2fs of audio in %.2fs (%.1fx real time)",
            seconds, elapsed, seconds / max(elapsed, 1e-6),
        )  # fmt: skip
        return full

    def _synth_segment(self, segment, lang, style, speed, cancel_event) -> np.ndarray:
        import onnxruntime as ort

        vocab = model_store.vocab()
        parts = []
        with self._lock:
            session = self._ensure_session()
            for phonemes in g2p.phoneme_chunks(segment, lang):
                if cancel_event is not None and cancel_event.is_set():
                    raise GenerationCancelled()
                ids = [vocab[c] for c in phonemes if c in vocab][: g2p.MAX_PHONEMES]
                if not ids:
                    continue
                run_options = ort.RunOptions()
                done = threading.Event()
                if cancel_event is not None:
                    _watch_cancel(cancel_event, done, run_options)
                try:
                    out = session.run(
                        None,
                        {
                            "input_ids": np.array([[0, *ids, 0]], dtype=np.int64),
                            "style": style[len(ids) - 1][None, :].astype(np.float32),
                            "speed": np.array([speed], dtype=np.float32),
                        },
                        run_options,
                    )[0]
                except Exception:
                    if cancel_event is not None and cancel_event.is_set():
                        raise GenerationCancelled() from None
                    raise
                finally:
                    done.set()
                parts.append(out.reshape(-1).astype(np.float32))
        return np.concatenate(parts) if parts else np.zeros(0, np.float32)


def _watch_cancel(cancel_event: threading.Event, done: threading.Event, run_options) -> None:
    """Abort the running model call as soon as cancel_event is set."""

    def watch():
        while not done.is_set():
            if cancel_event.wait(0.05):
                run_options.terminate = True
                return

    threading.Thread(target=watch, daemon=True).start()


def _check_range(name: str, value: float, bounds: tuple[float, float]) -> None:
    low, high = bounds
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low:g} and {high:g}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Speak text with Kokoro-82M.")
    parser.add_argument("text")
    parser.add_argument("--lang", default="a", choices=sorted(voices.LANGUAGES))
    parser.add_argument("--voice", help="voice id (default: the language's default voice)")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--pitch", type=float, default=0.0)
    parser.add_argument("--out", type=Path, default=Path("speech.wav"), help=".wav or .mp3")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    engine = KokoroEngine()
    voice = args.voice or voices.default_voice(args.lang).id
    result = engine.generate(args.text, args.lang, voice, args.speed, args.pitch)
    encode = audio.encode_mp3 if args.out.suffix.lower() == ".mp3" else audio.encode_wav
    args.out.write_bytes(encode(result))
    log.info("Wrote %s (%.1fs)", args.out, len(result) / SAMPLE_RATE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
