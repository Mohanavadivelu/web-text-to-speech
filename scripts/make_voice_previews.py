"""Make a short sample of every voice for the voice picker's preview button.

    python scripts/make_voice_previews.py

Writes web/public/previews/<voice id>.mp3 (served as static files, so previews
cost no API calls). Rerun only when the voices or preview sentences change.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.engine import audio, voices  # noqa: E402
from server.engine.synth import KokoroEngine  # noqa: E402

OUT = ROOT / "web" / "public" / "previews"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    engine = KokoroEngine()
    engine.load(warm_up=False)
    total = 0
    for voice in voices.VOICES.values():
        sentence = voices.LANGUAGES[voice.lang].preview_text
        data = audio.encode_mp3(engine.generate(sentence, voice.lang, voice.id))
        (OUT / f"{voice.id}.mp3").write_bytes(data)
        total += len(data)
    print(f"wrote {len(voices.VOICES)} previews ({total / 1024:.0f} KB) to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
