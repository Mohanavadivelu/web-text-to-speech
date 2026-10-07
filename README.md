# Kokoro TTS Web

The web version of [Kokoro TTS Studio](https://github.com/Mohanavadivelu/text-to-speech-app): natural-sounding text-to-speech in the browser, powered by the open [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) model.

> **Status:** planning. No application code yet.

## Planned features

- 7 languages and 37 voices, with voice mixing, speed and pitch
- Audio starts playing while it is still being generated
- Long texts and documents (`.txt`, `.md`, `.docx`, `.pdf`) as background jobs
- Clean pasted text and custom pronunciations
- MP3 download, with history for signed-in users

## Documents

| Document | Contents |
|---|---|
| [docs/WEB_STAGE1_PLAN.md](docs/WEB_STAGE1_PLAN.md) | Stage 1 (MVP) plan: architecture, API, limits, deployment, costs, timeline |
| [docs/DESIGN.md](docs/DESIGN.md) | Visual design spec from the desktop app (Studio Dark theme) |

## Relationship to the desktop app

The speech engine (`core/`) is developed in the desktop repo, [`text-to-speech-app`](https://github.com/Mohanavadivelu/text-to-speech-app), and copied into this repo by a sync script. See [§6 of the Stage 1 plan](docs/WEB_STAGE1_PLAN.md#6-repository-layout).
