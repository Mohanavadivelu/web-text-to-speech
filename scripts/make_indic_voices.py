"""Make the Indic-Mio voice embeddings (server/engines/indic_mio/voices/<id>.npy).

Each voice is the codec's 128-number speaker embedding of a reference recording:
  - "native" voices: the sample recordings on the Indic-Mio model card (Apache-2.0)
  - the others: Kokoro-82M reading a fixed passage in its own voices (Apache-2.0),
    so a voice like "Heart" sounds the same in both engines

Runs in the GPU image (it needs both engines), from the repository root:

    docker run --rm --gpus all -e HF_HUB_OFFLINE=0 -v "$PWD/server:/app/server" \\
      -v "$PWD/scripts:/app/scripts" narravo-gpu:dev python scripts/make_indic_voices.py

Rerun only when the voice list changes, and listen to the result before committing.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from server.engines.common import audio  # noqa: E402
from server.engines.indic_mio import model_store  # noqa: E402
from server.engines.indic_mio.voices import EMBEDDINGS_DIR, VOICES  # noqa: E402

REFERENCE_PASSAGE = (
    "The morning light spread slowly across the quiet valley. "
    "Birds began to sing, and somewhere far away, "
    "a train whistled as it crossed the old stone bridge."
)

# voice id -> where its reference recording comes from
SOURCES = {
    "in_ananya": ("indic_sample", "samples/sample1.wav"),  # Hinglish, female
    "in_vikram": ("indic_sample", "samples/sample2.wav"),  # English, male
    "in_arjun": ("indic_sample", "samples/sample3.wav"),  # Gujarati, male
    "in_karthik": ("indic_sample", "samples/sample4.wav"),  # Tamil, male
    "in_heart": ("kokoro", ("af_heart", "a")),
    "in_bella": ("kokoro", ("af_bella", "a")),
    "in_emma": ("kokoro", ("bf_emma", "b")),
    "in_michael": ("kokoro", ("am_michael", "a")),
    "in_fenrir": ("kokoro", ("am_fenrir", "a")),
    "in_george": ("kokoro", ("bm_george", "b")),
}


def main() -> int:
    import torch
    from huggingface_hub import hf_hub_download
    from miocodec import MioCodecModel
    from miocodec.util import load_audio

    from server.engines.kokoro.synth import KokoroEngine

    if set(SOURCES) != {v.id for v in VOICES}:
        raise SystemExit("Every voice in voices.py needs a source in SOURCES.")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    codec_dir = model_store.repo_dir(model_store.CODEC)
    codec = MioCodecModel.from_pretrained(
        config_path=str(codec_dir / "config.yaml"),
        weights_path=str(codec_dir / "model.safetensors"),
    )
    codec = codec.eval().to(device)
    kokoro = KokoroEngine()
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        for voice_id, (kind, source) in SOURCES.items():
            if kind == "indic_sample":
                path = hf_hub_download(
                    model_store.LM.repo_id, source, revision=model_store.LM.revision
                )
            else:
                kokoro_voice, lang = source
                path = Path(tmp) / f"{voice_id}.wav"
                speech = kokoro.generate(REFERENCE_PASSAGE, lang, kokoro_voice)
                path.write_bytes(audio.encode_wav(speech))
            waveform = load_audio(str(path), sample_rate=codec.config.sample_rate).to(device)
            with torch.inference_mode():
                features = codec.encode(waveform, return_content=False, return_global=True)
            embedding = features.global_embedding.float().cpu().numpy().reshape(-1)
            np.save(EMBEDDINGS_DIR / f"{voice_id}.npy", embedding.astype(np.float32))
            print(f"{voice_id:12} <- {kind}: {source}  ({embedding.shape[0]} values)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
