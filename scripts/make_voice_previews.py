"""Make a short sample of every voice for the voice picker's preview button.

    python scripts/make_voice_previews.py                     # Kokoro voices (CPU is fine)
    python scripts/make_voice_previews.py --engine indic_mio  # Indic voices (GPU image)

Writes web/public/previews/<voice id>.mp3 (served as static files, so previews cost
no API calls). Indic voices speak a Hindi greeting. Rerun only when the voices or
preview sentences change.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import engines  # noqa: E402
from server.engines.common import audio  # noqa: E402

OUT = ROOT / "web" / "public" / "previews"
INDIC_PREVIEW_LANG = "hi"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--engine", choices=engines.ENGINES, default="kokoro")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    engine = engines.create_engine(args.engine)
    engine.load(warm_up=False)
    languages = [lang for lang in engines.catalog() if lang.engine == args.engine]
    if args.engine == "indic_mio":  # every Indic voice speaks every language: one sample each
        languages = [lang for lang in languages if lang.code == INDIC_PREVIEW_LANG]

    total, count = 0, 0
    for lang in languages:
        for voice in lang.voices:
            data = audio.encode_mp3(engine.generate(lang.preview_text, lang.code, voice.id))
            (OUT / f"{voice.id}.mp3").write_bytes(data)
            total += len(data)
            count += 1
    print(f"wrote {count} previews ({total / 1024:.0f} KB) to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
