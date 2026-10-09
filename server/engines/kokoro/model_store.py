"""Kokoro model files: where they live, how to download them, and how to verify them.

Every file is pinned to one Hugging Face revision and checked by size and SHA-256,
so a build can never silently pick up a different model.

    <MODELS_DIR>/onnx/model.onnx
    <MODELS_DIR>/onnx/tokenizer.json
    <MODELS_DIR>/onnx/voices/<voice>.bin

Command line (used by the Docker build):

    python -m server.engines.kokoro.model_store download [--dir DIR]
    python -m server.engines.kokoro.model_store verify   [--dir DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)

REPO = "onnx-community/Kokoro-82M-v1.0-ONNX"
REVISION = "1939ad2a8e416c0acfeecc08a694d14ef25f2231"
VOICE_BYTES = 510 * 256 * 4

_MODEL_FILES = {
    # repo path: (size, sha256)
    "onnx/model.onnx": (
        325_532_232,
        "8fbea51ea711f2af382e88c833d9e288c6dc82ce5e98421ea61c058ce21a34cb",
    ),
    "tokenizer.json": (
        3_497,
        "77a02c8e164413299b4b4c403b14f8e0e1c1b727db4d46a09d6327b861060a34",
    ),
}

_VOICE_SHA256 = {
    "af_alloy": "c4a6b876047fd7fb472edf4ebd63cfac7c3b958a7cae7c106e8f038ca6308c45",
    "af_aoede": "4a004c33430762e2461eedb2013fad808ef4ab3121f5300f554476caf58d8361",
    "af_bella": "f69d836209b78eb8c66e75e3cda491e26ea838a3674257e9d4e5703cbaf55c8b",
    "af_heart": "d583ccff3cdca2f7fae535cb998ac07e9fcb90f09737b9a41fa2734ec44a8f0b",
    "af_kore": "9be5221b6a941c04b561959b8ff0b06e809444dcc4ab7e75a7b23606f691819e",
    "af_nicole": "cd2191ab31b914ed7b318416b0e4440fdf392ddad9106a060819aa600a64f59a",
    "af_nova": "18778272caa0d0eebaea251c35fd635f038434f9eee5e691d02a174bd328414f",
    "af_sarah": "4409fbc125afabacc615d94db5398d847006a737b0247d6892b7a9a0007a2f0a",
    "af_sky": "4435255c9744f3f31659e0d714ab7689bf65d9e77ec1cce060f083912614f0b9",
    "am_adam": "162b035ed91cfc48b6046982184c645f72edcdd1b82843347f605d7bf7b15716",
    "am_echo": "3968b92c3c4cd1c4416dbded36c13eaa388a90d5788d02a13e4d781f5f8cf3c3",
    "am_eric": "e8b5be17edd1e3636901ce7598baafe2dc8dd8ff707a0c23bf9e461add7e2832",
    "am_fenrir": "c27989f741f7ee34d273a39d8a595cc0837d35f5ced9a29b7cc162614616df43",
    "am_liam": "52403be32fd047c6a44517cb0bcd6b134f2a18baa73e70ef41651e0eab921ade",
    "am_michael": "1d1f21dd8da39c30705cd4c75d039d265e9bc4a2a93ed09bc9e1b1225eb95ba1",
    "am_puck": "fcf73c989033e9233e0b98713eca600c8c74dcc1614b37009d5450ff4a2274a0",
    "bf_alice": "08afa6ba24da61ea5e8efa139e5aadc938d83f0a6da5a900adaf763ac1da5573",
    "bf_emma": "669fe0647f9dd04fcab92f1439a40eeb4c8b4ab1f82e4996fe3d918ce4a63b73",
    "bf_isabella": "3754352c4aaa46d17f27654ab7518d65b62ad6163a0f55a5f4330c2da2c4e94f",
    "bf_lily": "5e0ee32ebe64a467124976b14e69590746f1c4ce41a12b587a50c862edfea335",
    "bm_daniel": "6b3194bbceffb746733cbc22c8f593dd44e401a71d53895a2dca891bc595a1e8",
    "bm_fable": "f889083196807b4adb15e9204252165f503b8d33d3982e681c52443c49d798f1",
    "bm_george": "c4b235a4c1f2cd3b939fed08b899ce9385638b763f7b73a59616c4fc9bd6c9bc",
    "bm_lewis": "b8f671cef828c30e66fdf0b0756a76bba58f6bb3398cbbf27058642acbcedb97",
    "ef_dora": "f66ec66bd295acb18372e37008533a9a3228483ccd294e7538d5d9294ac9a532",
    "em_alex": "27809e9eafdcbcfff90a3016c697568676531de2a2c39cee29c96c7bd6b83e95",
    "em_santa": "ad43b774e1ca24d05c6161297d8aeb770ac3d29bb95daf516727af5f7d543683",
    "ff_siwis": "a35f5675ad08948e326ae75fd0ea16ba5d0042e4f76b5f3d1df77d0a48c54861",
    "hf_alpha": "040be6a4425411cc01fda5fd06693c76bfa78572632852bc8cda9c99232ffb56",
    "hf_beta": "cd83ae0bb9b2e4e4fb92b4973bd8d1822ca0036d3c498bf4fc89aa8e33917cc7",
    "hm_omega": "b02d9222d9ed00ce26b302173a862c2c93f96cc40b5c422b8d14910b9ff34137",
    "hm_psi": "644daf88ba8aeb7bd08950bbdcd4453bb280864e49dc4df93fabc6be32e03f37",
    "if_sara": "409b69248798fcdc2542330c76953d230710f19b057e59cb82fdc3c4cf71265c",
    "im_nicola": "bc578e510d52a96d6940d46f12e96d7b3df00905dbea075113226d100e6e1ab0",
    "pf_dora": "3da7b5b2d91847ebf5646f57631af6ececae3c29a89cd300f06edf9aa6cfe9ee",
    "pm_alex": "0175c753f59c54e7fd5a995bedef0c5ff2fb67e0043dd3dcb2ae74ec2acbeb2a",
    "pm_santa": "8b012db3185778afe2e45a62cbad69db73021774fe68dda634bcc748a982eede",
}


@dataclass(frozen=True)
class RemoteFile:
    repo_path: str
    size: int
    sha256: str

    @property
    def url(self) -> str:
        return f"https://huggingface.co/{REPO}/resolve/{REVISION}/{self.repo_path}"

    def local_path(self, models_dir: Path) -> Path:
        name = self.repo_path.removeprefix("onnx/")
        return models_dir / "onnx" / name


FILES: list[RemoteFile] = [RemoteFile(p, size, sha) for p, (size, sha) in _MODEL_FILES.items()] + [
    RemoteFile(f"voices/{vid}.bin", VOICE_BYTES, sha) for vid, sha in sorted(_VOICE_SHA256.items())
]


def models_dir() -> Path:
    """MODELS_DIR from the environment, or <repo>/models."""
    default = Path(__file__).resolve().parents[3] / "models"
    return Path(os.environ.get("MODELS_DIR") or default).resolve()


def model_path() -> Path:
    return models_dir() / "onnx" / "model.onnx"


def voice_path(voice_id: str) -> Path:
    if voice_id not in _VOICE_SHA256:
        raise ValueError(f"Unknown voice '{voice_id}'.")
    return models_dir() / "onnx" / "voices" / f"{voice_id}.bin"


@lru_cache(maxsize=1)
def vocab() -> dict[str, int]:
    """Phoneme → token id map from tokenizer.json."""
    path = models_dir() / "onnx" / "tokenizer.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["model"]["vocab"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(4 << 20), b""):
            h.update(block)
    return h.hexdigest()


def problems(directory: Path | None = None, check_hashes: bool = True) -> list[str]:
    """Return a list of missing or damaged files (empty when everything is fine)."""
    directory = directory or models_dir()
    found = []
    for f in FILES:
        path = f.local_path(directory)
        if not path.is_file():
            found.append(f"missing: {f.repo_path}")
        elif path.stat().st_size != f.size:
            found.append(f"wrong size: {f.repo_path}")
        elif check_hashes and _sha256(path) != f.sha256:
            found.append(f"wrong hash: {f.repo_path}")
    return found


def _download(f: RemoteFile, dest: Path, timeout: int = 60) -> None:
    """Download one file with resume (.part) and verify it before moving it into place."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    if have > f.size:
        part.unlink()
        have = 0
    if have < f.size:
        req = urllib.request.Request(f.url, headers={"User-Agent": "narravo"})  # noqa: S310
        if have:
            req.add_header("Range", f"bytes={have}-")
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https URL)
            if have and resp.status != 206:  # server ignored Range: start over
                have = 0
            with open(part, "ab" if have else "wb") as out:
                while chunk := resp.read(1 << 20):
                    out.write(chunk)
    if part.stat().st_size != f.size:
        raise OSError(f"Download of {f.repo_path} is incomplete; run the command again.")
    if _sha256(part) != f.sha256:
        part.unlink()
        raise OSError(f"{f.repo_path} failed its integrity check.")
    os.replace(part, dest)


def download(directory: Path | None = None) -> int:
    """Download every missing or damaged file. Returns the number of files fetched."""
    directory = directory or models_dir()
    fetched = 0
    for f in FILES:
        path = f.local_path(directory)
        if path.is_file() and path.stat().st_size == f.size and _sha256(path) == f.sha256:
            continue
        log.info("Downloading %s (%.1f MB)", f.repo_path, f.size / 1e6)
        _download(f, path)
        fetched += 1
    return fetched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download or verify the Kokoro model files.")
    parser.add_argument("command", choices=["download", "verify"])
    parser.add_argument("--dir", type=Path, help="models directory (default: MODELS_DIR)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    directory = (args.dir or models_dir()).resolve()

    if args.command == "download":
        fetched = download(directory)
        log.info("%d file(s) downloaded into %s", fetched, directory)
    issues = problems(directory)
    for issue in issues:
        log.error(issue)
    if not issues:
        log.info("All %d model files verified in %s", len(FILES), directory)
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
