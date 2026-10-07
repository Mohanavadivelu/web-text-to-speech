# Kokoro TTS Web

Natural-sounding text-to-speech in the browser, powered by the open [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) model. Paste text or open a document, pick a voice, and hear it within seconds.

> **Status:** planning. The design and plans are complete; application code starts with milestone M0 of the [development plan](docs/DEVELOPMENT_PLAN.md).

## Features (Stage 1)

- **7 languages, 37 voices:** American and British English, Hindi, French, Italian, Spanish and Brazilian Portuguese
- **Voice mixing:** blend two voices from 10% to 90%
- **Speed and pitch** controls, with instant voice previews
- **Live playback:** audio starts playing while the rest is still being generated
- **Long texts and documents:** `.txt`, `.md`, `.docx` and `.pdf`, generated as background jobs with progress and cancel
- **Clean text:** one click fixes pasted text (curly quotes, links, markdown symbols, lines broken mid-sentence in PDFs)
- **Custom pronunciations** for names and acronyms, saved to your account
- **MP3 download** (WAV for signed-in users) and a 7-day history
- **Free to use**, with or without an account; daily limits keep it fair
- **Private by design:** your text is never stored or logged

## How it works

```
Browser ──► Cloudflare (CDN, WAF) ──► FastAPI ──► Redis queue ──► Workers (Kokoro on ONNX Runtime)
                                         │                              │
                                         ▼                              ▼
                               Supabase (accounts)          Cloudflare R2 (audio files)
```

Every request becomes a job. A worker turns the text into speech segment by segment and streams each piece back to the browser over a WebSocket, then stores the finished MP3 in R2. Stage 1 runs on a single CPU server for about **$40–120 a month**. Details are in the [Stage 1 plan](docs/WEB_STAGE1_PLAN.md).

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite; hosted on Cloudflare Pages |
| API | Python 3.12, FastAPI, WebSockets |
| Jobs | arq on Redis |
| Speech engine | Kokoro-82M on ONNX Runtime (CPU), misaki and espeak-ng for phonemes |
| Data and auth | Supabase (Postgres, email-link and Google sign-in) |
| Audio storage | Cloudflare R2 |
| Hosting | Hetzner VM with Docker Compose and Caddy |
| Monitoring | Sentry, uptime checks, Grafana Cloud |

## Project structure (planned)

```
server/
  engine/     speech engine: text → audio (no web code)
  api/        FastAPI app: jobs, streaming, files, accounts, limits
  worker/     job runner: engine → live chunks → R2
web/          React frontend
docs/         design and plans
scripts/      benchmarks, voice previews, backups
```

## Documents

| Document | Contents |
|---|---|
| [docs/WEB_STAGE1_PLAN.md](docs/WEB_STAGE1_PLAN.md) | Stage 1 (MVP) plan: scope, architecture, speech engine, API, limits, deployment, costs |
| [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md) | Task-by-task build plan: milestones, estimates, done criteria, local setup |
| [docs/DESIGN.md](docs/DESIGN.md) | Web UI design spec: tokens, layouts, components, states, accessibility |
| [CHANGELOG.md](CHANGELOG.md) | Notable changes |
| [SECURITY.md](SECURITY.md) | How to report a vulnerability, and how the service protects users |

## Roadmap

| Milestone | Goal |
|---|---|
| M0 | Project setup: tooling, CI, accounts |
| M1 | Speech engine |
| M2 | Worker and Docker image |
| M3 | API with live streaming |
| M4 | Web frontend |
| M5 | Accounts and limits |
| M6 | Production deployment and monitoring |
| M7 | Private beta, then public launch |

## Getting started

There's nothing to run yet. Local development instructions are in [§12 of the development plan](docs/DEVELOPMENT_PLAN.md#12-local-development-setup) and will move here once M0 is done.

## Acknowledgements

- [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) by hexgrad (Apache-2.0)
- [misaki](https://github.com/hexgrad/misaki) (MIT) and [espeak-ng](https://github.com/espeak-ng/espeak-ng) (GPL-3.0) for text-to-phoneme conversion
- [ONNX Runtime](https://onnxruntime.ai) (MIT)
