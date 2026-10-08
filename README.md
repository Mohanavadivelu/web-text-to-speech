# Kokoro TTS Web

Natural-sounding text-to-speech in the browser, powered by the open [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) model. Paste text or open a document, pick a voice, and hear it within seconds.

> **Status:** early development. M0–M4 are done: setup, speech engine, workers, API and the web Studio. Next is M5 (accounts and limits). See the [development plan](docs/DEVELOPMENT_PLAN.md).

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

## Project structure

```
server/
  engine/     speech engine: text → audio (no web code)
  api/        FastAPI app: jobs, streaming, files, accounts, limits
  worker/     job runner: engine → live chunks → R2
web/          React frontend
supabase/     Supabase CLI project: auth config and database migrations
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

You need Python 3.11 or 3.12, Node 22+ and Docker Desktop.

**API** (from the repository root):

```bash
python -m venv .venv
.venv/Scripts/activate            # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn server.api.main:app --reload          # http://localhost:8000/v1/health
```

**Speech engine** (downloads the 330 MB model once, then speaks a sentence):

```bash
python -m server.engine.model_store download
python -m server.engine.synth "Hello there." --voice af_heart --out hello.wav
```

**Whole stack** (Redis, local S3 storage, API and a speech worker, in Docker):

```bash
docker compose -f server/docker-compose.yml up --build -d
python scripts/try_job.py "Hello from the API."        # create a job, stream it live, download the MP3
python scripts/benchmark.py --jobs 8                   # many jobs at once
```

The API runs on http://localhost:8000; its interactive docs are at http://localhost:8000/docs. For example:

```bash
curl -c cookies.txt -H "Content-Type: application/json"      -d '{"text": "Hello there.", "voice": "af_heart"}' http://localhost:8000/v1/tts/jobs
curl -b cookies.txt http://localhost:8000/v1/tts/jobs/<id>      # status and, when done, an MP3 link
```

Live audio comes over the WebSocket at `stream_url` (JSON status messages plus binary PCM16 audio). After changing the API, run `python scripts/export_openapi.py` and `npm run api:types` in `web/` to update the frontend's types.

**Web app** (with the Docker stack running):

```bash
cd web
npm install
npm run dev                                    # http://localhost:5173 (proxies /v1 to :8000)
npm run e2e                                    # browser tests (Playwright; first: npx playwright install chromium)
```

**Checks** (the same ones CI runs):

```bash
ruff check . && ruff format --check . && pytest       # model tests skip until the model is downloaded
cd web && npm run lint && npm run format:check && npm run typecheck && npm test && npm run build
```

**Supabase** (accounts and database), once per machine:

```bash
npx supabase login                                     # opens the browser
npx supabase link --project-ref fewhxkyzbmwtegekiyxp   # asks for the database password
```

Copy `.env.example` to `.env` for local settings. The full local setup is in [§12 of the development plan](docs/DEVELOPMENT_PLAN.md#12-local-development-setup).

## Acknowledgements

- [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) by hexgrad (Apache-2.0)
- [misaki](https://github.com/hexgrad/misaki) (MIT) and [espeak-ng](https://github.com/espeak-ng/espeak-ng) (GPL-3.0) for text-to-phoneme conversion
- [ONNX Runtime](https://onnxruntime.ai) (MIT)
