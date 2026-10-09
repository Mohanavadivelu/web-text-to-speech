"""Indic-Mio model files: pinned versions, download and verification.

Two Hugging Face repositories, each pinned to one commit; the large weight files are
checked by SHA-256 so a build can never pick up different weights.

    <MODELS_DIR>/indic_mio/lm/      SPRINGLab/Indic-Mio (Qwen3-0.6B fine-tune, Apache-2.0)
    <MODELS_DIR>/indic_mio/codec/   Aratako/MioCodec-25Hz-24kHz (MIT)

Command line (used by the GPU Docker build):

    python -m server.engines.indic_mio.model_store download [--dir DIR]
    python -m server.engines.indic_mio.model_store verify   [--dir DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Repo:
    folder: str
    repo_id: str
    revision: str
    files: tuple[str, ...]
    sha256: dict[str, str]  # large files checked by hash


LM = Repo(
    folder="lm",
    repo_id="SPRINGLab/Indic-Mio",
    revision="25feace00ca76c71c40b1e8d921fd3c2943c545e",
    files=(
        "added_tokens.json",
        "chat_template.jinja",
        "config.json",
        "generation_config.json",
        "merges.txt",
        "model.safetensors",
        "special_tokens_map.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "vocab.json",
    ),
    sha256={
        "model.safetensors": "065f42f7ab6148b66f43e9be0d01ac336343dfe16161350c37b71a87c3e1981b",
        "tokenizer.json": "abcde038b87ccd029a4523b0c5cec1da6d84b4f3d68b351495df086d63033f1f",
    },
)

CODEC = Repo(
    folder="codec",
    repo_id="Aratako/MioCodec-25Hz-24kHz",
    revision="3a737f0de2c6324cb2fe40c1fbd1056c7add423d",
    files=("config.yaml", "model.safetensors"),
    sha256={
        "model.safetensors": "60483759cde136451d53ff5a2f7e283c015758ab540de9037b5d4519366a7705",
    },
)

REPOS = (LM, CODEC)

# MioCodec builds a WavLM feature extractor when it loads, which torchaudio would
# otherwise download at runtime into $TORCH_HOME/hub/checkpoints (the GPU image sets
# TORCH_HOME=<MODELS_DIR>/torch so it's found offline).
WAVLM_URL = "https://download.pytorch.org/torchaudio/models/wavlm_base_plus.pth"
WAVLM_SIZE = 377_604_347
WAVLM_SHA256 = "136a3e720c04f2c77bf7a4dc6a3868b14d5a2c145a988114b733cb1a8428be98"


def wavlm_path(directory: Path | None = None) -> Path:
    return (directory or models_dir()) / "torch" / "hub" / "checkpoints" / "wavlm_base_plus.pth"


def models_dir() -> Path:
    """MODELS_DIR from the environment, or <repo>/models."""
    default = Path(__file__).resolve().parents[3] / "models"
    return Path(os.environ.get("MODELS_DIR") or default).resolve()


def repo_dir(repo: Repo, directory: Path | None = None) -> Path:
    return (directory or models_dir()) / "indic_mio" / repo.folder


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(4 << 20), b""):
            h.update(block)
    return h.hexdigest()


def problems(directory: Path | None = None, check_hashes: bool = True) -> list[str]:
    """Missing or damaged files (empty when everything is fine)."""
    found = []
    for repo in REPOS:
        base = repo_dir(repo, directory)
        for name in repo.files:
            path = base / name
            if not path.is_file():
                found.append(f"missing: {repo.repo_id}/{name}")
            elif check_hashes and name in repo.sha256 and _sha256(path) != repo.sha256[name]:
                found.append(f"wrong hash: {repo.repo_id}/{name}")
    wavlm = wavlm_path(directory)
    if not wavlm.is_file() or wavlm.stat().st_size != WAVLM_SIZE:
        found.append("missing: wavlm_base_plus.pth")
    elif check_hashes and _sha256(wavlm) != WAVLM_SHA256:
        found.append("wrong hash: wavlm_base_plus.pth")
    return found


def download(directory: Path | None = None) -> None:
    from huggingface_hub import hf_hub_download

    for repo in REPOS:
        target = repo_dir(repo, directory)
        for name in repo.files:
            log.info("Fetching %s/%s", repo.repo_id, name)
            hf_hub_download(repo.repo_id, name, revision=repo.revision, local_dir=target)
    wavlm = wavlm_path(directory)
    if not wavlm.is_file() or wavlm.stat().st_size != WAVLM_SIZE:
        log.info("Fetching wavlm_base_plus.pth")
        wavlm.parent.mkdir(parents=True, exist_ok=True)
        part = wavlm.with_suffix(".part")
        urllib.request.urlretrieve(WAVLM_URL, part)  # noqa: S310 (fixed https URL)
        if _sha256(part) != WAVLM_SHA256:
            part.unlink()
            raise OSError("wavlm_base_plus.pth failed its integrity check.")
        part.replace(wavlm)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download or verify the Indic-Mio model files.")
    parser.add_argument("command", choices=["download", "verify"])
    parser.add_argument("--dir", type=Path, help="models directory (default: MODELS_DIR)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    directory = (args.dir or models_dir()).resolve()
    if args.command == "download":
        download(directory)
    issues = problems(directory)
    for issue in issues:
        log.error(issue)
    if not issues:
        log.info("All Indic-Mio model files verified in %s", directory / "indic_mio")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
