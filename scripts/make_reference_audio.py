"""Generate the reference clips used by the engine's reference-audio tests.

Run on Linux, like production (from the repository root):

    docker run --rm -v "$PWD:/app" -w /app python:3.12-slim sh -c \
      "pip install -q -r server/requirements.txt && python scripts/make_reference_audio.py"

Only regenerate when a change to the voice is intended, and listen to every clip
before committing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.engine import audio, voices  # noqa: E402
from server.engine.synth import KokoroEngine  # noqa: E402
from server.tests.engine.reference import REFERENCE_DIR, REFERENCE_TEXTS, clip_path  # noqa: E402


def main() -> int:
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    engine = KokoroEngine()
    engine.load(warm_up=False)
    for lang, sentence in REFERENCE_TEXTS.items():
        result = engine.generate(sentence, lang, voices.default_voice(lang).id)
        clip_path(lang).write_bytes(audio.encode_wav(result))
        print(f"{lang}: {len(result) / audio.SAMPLE_RATE:.2f}s -> {clip_path(lang)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
