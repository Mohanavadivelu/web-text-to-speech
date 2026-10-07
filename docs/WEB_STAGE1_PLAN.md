# Kokoro TTS Web: Stage 1 Plan (MVP launch)

> **Goal:** launch a text-to-speech web app built on the open Kokoro-82M model for the first ~1,000 users, at a running cost of **about $40–120 a month**, with a clear path to Stage 2 (GPU, more users).
>
> **Status:** proposal, October 2026. All prices are approximate list prices and should be checked before you buy anything.

---

## Table of Contents

1. [Scope](#1-scope)
2. [Target numbers](#2-target-numbers)
3. [Architecture](#3-architecture)
4. [Technology choices](#4-technology-choices)
5. [Speech engine](#5-speech-engine)
6. [Repository layout](#6-repository-layout)
7. [API design](#7-api-design)
8. [Job flow and streaming](#8-job-flow-and-streaming)
9. [Web frontend](#9-web-frontend)
10. [Accounts, limits and abuse protection](#10-accounts-limits-and-abuse-protection)
11. [Storage and audio formats](#11-storage-and-audio-formats)
12. [Deployment](#12-deployment)
13. [Monitoring and operations](#13-monitoring-and-operations)
14. [Security and privacy](#14-security-and-privacy)
15. [Licensing](#15-licensing)
16. [Capacity planning](#16-capacity-planning)
17. [Cost plan](#17-cost-plan)
18. [Timeline](#18-timeline)
19. [Testing and launch checklist](#19-testing-and-launch-checklist)
20. [When to move to Stage 2](#20-when-to-move-to-stage-2)
21. [Risks and open questions](#21-risks-and-open-questions)

---

## 1. Scope

### In scope (Stage 1)

| Feature | Notes |
|---|---|
| Type or paste text and generate speech | 7 languages and 37 voices |
| Voice, speed and pitch controls | Speed 0.5–2.0×, pitch ±6 semitones |
| Voice mixing (two voices, 10–90%) | Blends the two voices' style tables in the engine |
| Live playback while generating | Audio starts within a few seconds; see [§8](#8-job-flow-and-streaming) |
| Long texts (articles, chapters) | Background jobs with a progress bar and cancel |
| Open `.txt`, `.md`, `.docx` and `.pdf` | Parsed on the server with size and time limits |
| Clean text | Fixes pasted text: curly quotes, links, markdown symbols, lines broken mid-sentence in PDFs |
| Custom pronunciations | Saved per account; plain spellings or phonemes |
| Download MP3 | WAV for signed-in users |
| History of recent generations | Signed-in users only, kept for 7 days |
| Free use without an account | With tighter limits |
| Sign in with an email link or Google | Higher limits, history, saved pronunciations |

### Out of scope (later stages)

- Payments and paid plans (Stage 1 is free; add Stripe once demand is proven)
- GPU inference (CPU is enough at this volume; see [§16](#16-capacity-planning))
- Public developer API and API keys
- Voice cloning or custom voices
- Mobile apps
- Multiple regions and high availability. A single server is acceptable for an MVP, and the cost of an outage is low.

---

## 2. Target numbers

| Metric | Stage 1 target |
|---|---|
| Registered users | up to ~1,000 |
| Generated audio | ~200 audio-hours per month (≈ 11 million characters) |
| Peak concurrent generations | 4–6 |
| Time to first audio (short text) | under 3 seconds |
| Long job throughput | at least 2× real time per job |
| Uptime | best effort, about 99% |
| Monthly running cost | $40–120 |

---

## 3. Architecture

```
                    ┌──────────────────────────────────────────┐
  Browser  ───────► │ Cloudflare (DNS, CDN, WAF, Turnstile)    │
                    └───────────────┬──────────────────────────┘
          static files              │ /api, /ws
     ┌──────────────────┐           ▼
     │ Cloudflare Pages │   ┌────────────────── VM (Hetzner, Docker Compose) ──────────────┐
     │ (web frontend)   │   │                                                             │
     └──────────────────┘   │  Caddy (TLS) ──► api (FastAPI, uvicorn, 2 processes)        │
                            │                    │  ▲                                     │
                            │                    ▼  │ pub/sub: progress + audio chunks    │
                            │                  Redis (job queue, rate limits, pub/sub)   │
                            │                    │  ▲                                     │
                            │                    ▼  │                                     │
                            │                  worker ×N (ONNX engine, model in RAM)      │
                            └────────────┬─────────────────────────────┬──────────────────┘
                                         │                             │
                                         ▼                             ▼
                              Supabase (Postgres + Auth)     Cloudflare R2 (audio files)
                                                                       │
                                                  signed download URLs ┘──► Browser
```

The design follows four principles:

1. **The API is stateless and does no inference.** It authenticates, validates, enforces limits, queues jobs and relays progress. That way the API stays responsive while workers are busy.
2. **Workers are the only processes that load the model.** Each worker loads Kokoro once and keeps it in memory, so you scale by adding workers.
3. **Every generation is a job.** Short texts and long documents take the same path. The only difference is that the browser plays chunks as they arrive. One path means less code and fewer bugs.
4. **Workers and the API share nothing except Redis, Postgres and R2.** In Stage 2, workers can move to GPU machines (or serverless GPU) without changing the API.

---

## 4. Technology choices

| Layer | Choice | Why | Alternative |
|---|---|---|---|
| Frontend | **React + Vite + TypeScript**, static build | Simple, cheap to host, no server rendering needed | Next.js (more than needed for this) |
| Frontend hosting | **Cloudflare Pages** | Free, global CDN, same provider as DNS and R2 | Vercel, Netlify |
| API | **FastAPI** (Python 3.12) | Same language as the speech engine, async WebSockets, automatic OpenAPI docs | Flask (no native async) |
| Job queue | **arq** on Redis | Async, small, supports job abort, enough for this scale | RQ, Celery (heavier) |
| Workers | Python processes running the speech engine ([§5](#5-speech-engine)) on ONNX Runtime (CPU) | No GPU needed at Stage 1 volume; the same model can move to GPU later | PyTorch (larger image, needs a GPU to be fast) |
| Cache, rate limits, pub/sub | **Redis 7** (in Docker) | One service covers all three | Upstash (managed) |
| Database + auth | **Supabase** (free tier) | Postgres plus email-link and Google sign-in with no auth code to write | Neon + Auth.js / Clerk |
| Audio storage | **Cloudflare R2** | No egress fees; audio downloads are the main bandwidth cost | Backblaze B2, S3 (egress fees) |
| Server | **Hetzner** dedicated-vCPU VM | Best CPU price-performance for ONNX inference | DigitalOcean, OVH, Fly.io |
| TLS / reverse proxy | **Caddy** | Automatic certificates, one-line config | Nginx + certbot |
| Bot protection | **Cloudflare Turnstile** | Free, invisible captcha | hCaptcha |
| Errors | **Sentry** (free tier) | Frontend and backend errors in one place | GlitchTip (self-hosted) |
| Uptime | **Better Stack** or **UptimeRobot** (free) | External health check with alerts | — |

---

## 5. Speech engine

The engine is a Python package in `server/engine/`. It contains no web code: it turns text into audio and nothing else, so the worker, tests and benchmark scripts can all use it directly.

### Pipeline

```
text ─► pronunciations ─► segments ─► G2P ─► phoneme packing ─► Kokoro-82M (ONNX) ─► speed / pitch ─► audio chunk
                          ≤800 chars   misaki (English)   ≤510 per call   + voice style table               24 kHz mono
                          first ≤150   espeak-ng (others)                                                    float32
                          when streaming
```

- **Segments:** text is split at paragraph and sentence boundaries into segments of up to 800 characters. When streaming, the **first segment is a single sentence of up to ~150 characters**, so the first audio is ready in 1–2 s instead of the 15–20 s a full 800-character segment takes on CPU.
- **G2P:** misaki converts English (US and UK) to phonemes; espeak-ng handles Hindi, French, Italian, Spanish and Brazilian Portuguese.
- **Phoneme packing:** sentences are packed into model calls of up to 510 phonemes, the model's limit. Kokoro's pacing depends on chunk length, so packing to the full length keeps the speech rate natural.
- **Voices:** each voice is a style table. Mixing two voices is a weighted average of their tables (10–90%).
- **Speed and pitch:** speed is a model input; pitch (±6 semitones) is a resample after synthesis, with speed compensated so the duration stays the same.
- **Callbacks:** `generate()` takes `on_chunk(audio)`, `on_progress(percent)` and a `cancel_event`. Cancel is checked between segments and also stops a running model call through ONNX Runtime's `RunOptions.terminate`, so it takes effect in well under a second.
- **Model loading:** each worker process loads the model once at startup and keeps it in memory (~1.2–1.6 GB while generating).

### Modules

| Module | Responsibility |
|---|---|
| `engine/synth.py` | `KokoroEngine`: model session, segmenting, packing, callbacks, cancel, measured real-time factor |
| `engine/g2p.py` | misaki and espeak-ng set-up per language |
| `engine/voices.py` | Languages, the 37 voices with quality grades, defaults, style tables and blending |
| `engine/text.py` | `clean_text`, `count_words`, `estimate_seconds`, `apply_pronunciations`, and text extraction from `.txt/.md/.docx/.pdf` |
| `engine/model_store.py` | Downloads the model and voices from Hugging Face at pinned revisions and checks each file's SHA-256 |
| `engine/audio.py` | PCM16 conversion, MP3 and WAV encoding |

### Dependencies

`server/requirements.txt` pins:
- engine: numpy, onnxruntime, soundfile, misaki, spacy, num2words, espeakng-loader, phonemizer-fork, loguru, python-docx, pypdf
- server: fastapi, uvicorn, arq, redis, boto3 (for R2), PyJWT and sentry-sdk

### Built into the Docker image

The image installs `espeak-ng` (apt) and the spaCy English model misaki needs, and downloads the Kokoro ONNX model and voices with `model_store` during the build. It will be roughly 1.5 GB, and containers start in seconds with no network calls.

### Reference-audio tests

A fixed set of sentences (at least one per language) is synthesised and compared with stored reference clips using spectral correlation, which must be at least 0.997. This catches silent changes in the voice when onnxruntime, misaki, spaCy or espeak-ng are upgraded.

---

## 6. Repository layout

```
web-text-to-speech/
├── server/
│   ├── engine/                speech engine (§5); no web code
│   │   ├── synth.py
│   │   ├── g2p.py
│   │   ├── voices.py
│   │   ├── text.py
│   │   ├── model_store.py
│   │   └── audio.py
│   ├── api/
│   │   ├── main.py            FastAPI app, routers, CORS, Sentry
│   │   ├── auth.py            Supabase JWT verification, anonymous IDs
│   │   ├── limits.py          quotas and rate limits (Redis)
│   │   ├── routes_tts.py      jobs, WebSocket, cancel
│   │   ├── routes_files.py    document upload → text
│   │   ├── routes_user.py     history, pronunciations
│   │   └── schemas.py         Pydantic request/response models
│   ├── worker/
│   │   ├── main.py            arq WorkerSettings, loads the engine once at startup
│   │   ├── jobs.py            runs a job: engine → Redis chunks → R2
│   │   └── storage.py         R2 upload and signed URLs
│   ├── tests/                 includes the reference audio clips
│   ├── Dockerfile             one image, two commands (api / worker)
│   ├── docker-compose.yml     caddy, api, worker, redis
│   ├── Caddyfile
│   └── requirements.txt
├── web/
│   ├── src/
│   │   ├── pages/             Studio, History, Sign in, About, Privacy, Terms
│   │   ├── components/        TextEditor, VoicePanel, PlayerBar, Waveform, Pronunciations, Toast
│   │   ├── audio/             streaming player (Web Audio API)
│   │   ├── styles/tokens.css  design tokens from DESIGN.md
│   │   └── api/               typed client generated from OpenAPI
│   ├── index.html
│   └── package.json
├── supabase/                  Supabase CLI project: config.toml, migrations/
├── docs/
│   ├── DESIGN.md              web UI design spec
│   ├── WEB_STAGE1_PLAN.md     this document
│   └── DEVELOPMENT_PLAN.md    task-by-task build plan
├── scripts/                   benchmark, voice previews, backups
├── .github/workflows/         CI and deploy
├── CHANGELOG.md
├── SECURITY.md
└── README.md
```

---

## 7. API design

All endpoints are under `/v1`. Requests and responses are JSON unless noted. Authentication is a Supabase JWT in `Authorization: Bearer …`; requests without one count as anonymous and are identified by a signed `anon_id` cookie plus their IP address.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/health` | Liveness: checks Redis and the database, and that at least one worker is alive |
| `GET` | `/v1/voices` | Languages, voices, grades and defaults (from `engine/voices.py`) |
| `GET` | `/v1/me/usage` | Characters used today and the user's limits |
| `POST` | `/v1/tts/jobs` | Create a generation job |
| `GET` | `/v1/tts/jobs/{id}` | Job status, progress, download URL when finished |
| `DELETE` | `/v1/tts/jobs/{id}` | Cancel a job |
| `WS` | `/v1/tts/jobs/{id}/stream` | Live progress and audio chunks |
| `POST` | `/v1/files/extract` | Upload `.txt/.md/.docx/.pdf` (multipart) and get the extracted text back |
| `POST` | `/v1/text/clean` | Clean pasted text (`engine/text.py`) |
| `GET` / `PUT` | `/v1/me/pronunciations` | Read and replace the user's pronunciation list |
| `GET` | `/v1/me/history` | Recent jobs with fresh signed download URLs |

### `POST /v1/tts/jobs`

```json
{
  "text": "Hello from Kokoro on the web.",
  "lang": "a",
  "voice": "af_heart",
  "blend_voice": "af_bella",
  "blend_ratio": 0.3,
  "speed": 1.0,
  "pitch": 0.0,
  "format": "mp3",
  "stream": true,
  "turnstile_token": "…"
}
```

Validation:
- `voice` and `blend_voice` must belong to `lang`
- `speed` 0.5–2.0, `pitch` −6 to +6 semitones, `blend_ratio` 0.1–0.9
- text length within the per-request limit for the user's tier ([§10](#10-accounts-limits-and-abuse-protection))
- `turnstile_token` is required for anonymous users

Response `201`:

```json
{
  "id": "j_01JB…",
  "status": "queued",
  "position": 0,
  "estimated_seconds": 4.2,
  "stream_url": "/v1/tts/jobs/j_01JB…/stream"
}
```

### WebSocket messages (server → browser)

```jsonc
{ "type": "started", "segments": 6, "sample_rate": 24000 }
// followed by binary frames: PCM16 mono, 24 kHz, one per segment
{ "type": "progress", "percent": 50 }
{ "type": "done", "url": "https://audio.example.com/…signed…", "duration": 41.3 }
{ "type": "error", "message": "The engine produced no audio for this text." }
{ "type": "cancelled" }
```

Error responses use one shape: `{"error": {"code": "quota_exceeded", "message": "…"}}`. The codes are `invalid_input`, `quota_exceeded`, `rate_limited`, `too_long`, `busy` (queue full), `not_found` and `internal`.

---

## 8. Job flow and streaming

```
browser                api                    redis                 worker
   │ POST /tts/jobs     │                        │                      │
   │───────────────────►│ check limits, insert   │                      │
   │                    │ job row (Postgres)     │                      │
   │                    │ enqueue ──────────────►│                      │
   │◄── 201 {id} ───────│                        │◄──── pick up job ────│
   │ WS /stream ───────►│ subscribe job:{id} ───►│                      │
   │                    │                        │◄─ publish chunk ─────│ engine.generate(
   │◄── binary PCM ─────│◄───────────────────────│                      │   on_chunk=…, on_progress=…)
   │◄── progress ───────│◄───────────────────────│◄─ publish progress ──│
   │                    │                        │                      │ encode MP3 → upload R2
   │◄── done {url} ─────│◄───────────────────────│◄─ publish done ──────│ update job row
```

Details:

- **Chunks:** the worker passes `on_chunk` and `on_progress` callbacks to the engine's `generate()`. The worker converts each float32 chunk to PCM16 (48 KB per second of audio) and publishes it to the Redis channel `job:{id}`. It also appends the chunk to a short-lived Redis list, so a browser that reconnects can replay what it missed.
- **First audio quickly:** with the short first segment from [§5](#5-speech-engine), the first chunk is about one sentence. On a modern CPU that takes roughly 1–2 s.
- **Cancel:** `DELETE /jobs/{id}` sets `cancel:{id}` in Redis. A small thread in the worker watches for it and sets the engine's `cancel_event`, which also stops the running model call ([§5](#5-speech-engine)).
- **Timeouts:** a job is killed after `max(60 s, 3 × estimated time)`. arq retries a job once only if the worker crashed, not if the input was bad.
- **Final file:** when generation finishes, the worker encodes MP3 (64 kbps mono) with `soundfile`, uploads it to R2 at `audio/users/{user_id}/{job_id}.mp3` (or `audio/anon/{anon_id}/…`) and stores the key in Postgres. The browser receives a signed URL that is valid for 1 hour.
- **Queue fairness:** each user can have at most 1 running job and 2 queued. When the queue holds more than 30 jobs, the API returns `busy` to anonymous users first.
- **Cache:** a key of `sha256(text + lang + voice + blend + speed + pitch + model version)` points to an existing R2 file. A repeated request returns immediately without using any compute.

---

## 9. Web frontend

The full visual spec (Studio Dark theme, layouts, components, states, shortcuts) is in [DESIGN.md](DESIGN.md). The screens are:

| Screen | Contents |
|---|---|
| **Studio** (home) | Text editor with word count and estimated duration; buttons for Open file, Clean text, Pronunciations; voice settings panel (language, voice, mix, speed, pitch, voice preview); player bar with waveform, play/pause, seek, download |
| **History** | Signed-in users: last 7 days of generations with play and download |
| **Sign in** | Email link or Google (Supabase Auth UI) |
| **About / Privacy / Terms** | Required before launch ([§14](#14-security-and-privacy)) |

Implementation notes:
- **Streaming playback:** an `AudioContext` at 24 kHz; each PCM16 frame becomes an `AudioBuffer` and is scheduled right after the previous one. When the job finishes, the player switches to the MP3 URL so the user can seek and download.
- **Voice previews:** generate one short sample per voice once at build time, store them in R2 and serve them as static files. Previews then cost no compute.
- **Draft saving:** keep the unsent text in `localStorage`, so a refresh doesn't lose it.
- **Long texts:** show progress and an estimated finish time. Generation continues on the server if the user closes the tab; signed-in users find the result in History.
- **Mobile:** single-column layout below 768 px, with voice settings in a bottom sheet.
- **Accessibility:** full keyboard use, labelled controls, honour reduced-motion for the waveform.

---

## 10. Accounts, limits and abuse protection

| Limit | Anonymous | Signed in (free) |
|---|---|---|
| Characters per request | 2,000 | 20,000 |
| Characters per day | 10,000 | 100,000 |
| Uploaded file size | — (sign-in required) | 5 MB, PDF up to 200 pages |
| Running / queued jobs | 1 / 1 | 1 / 2 |
| Requests per minute | 10 | 30 |
| History | none | 7 days |
| Download formats | MP3 | MP3, WAV |

These are starting values; keep them in config so they can change without a deploy.

**How the limits are enforced:**
- Daily character counters live in Redis (`usage:{subject}:{yyyymmdd}`, expiring after 48 h) and are written to Postgres for reporting.
- Rate limits use a sliding window in Redis, keyed by user ID, or for anonymous users by `anon_id` and IP.
- Cloudflare's WAF rate rule is a second line of defence: 60 requests per minute per IP on `/v1/tts/*`.
- Turnstile is required for anonymous job creation and for sign-up.
- Unusual use (for example one IP creating many anonymous IDs) is logged and can be blocked by IP or ASN in Cloudflare.

**Database tables (Supabase Postgres):**

```sql
profiles        (id uuid pk → auth.users, created_at, tier text default 'free')
jobs            (id text pk, user_id uuid null, anon_id text null, status text,
                 lang text, voice text, blend_voice text, blend_ratio real,
                 speed real, pitch real, chars int, audio_seconds real,
                 cache_key text, r2_key text, error text,
                 created_at, started_at, finished_at)
pronunciations  (user_id uuid, word text, say text, primary key (user_id, word))
usage_daily     (subject text, day date, chars int, jobs int, primary key (subject, day))
```

The `jobs` table does not store the input text (see [§14](#14-security-and-privacy)). Row-level security makes each user able to read only their own rows. The API writes with the secret key (`sb_secret_…`), which is never sent to the browser.

---

## 11. Storage and audio formats

| Use | Format | Size per audio hour |
|---|---|---|
| Live streaming | PCM16, 24 kHz mono (WebSocket) | ~173 MB (sent, not stored) |
| Stored file / download | MP3, 64 kbps mono | ~29 MB |
| WAV download (signed in) | PCM16 WAV written at generation time, kept in R2 for 24 h only (not made from the MP3, which would lose quality) | ~173 MB |

Live streaming moves the most data. For texts over ~5 minutes of audio, a later step is to stream Opus instead of PCM, which is about 10× smaller. In Stage 1, streaming goes through Hetzner, where 20 TB of traffic is included, so PCM costs nothing extra.

**R2 lifecycle rules:**
- `audio/anon/*`: delete after 1 day
- `audio/users/*`: delete after 7 days
- `wav/*`: delete after 1 day
- `previews/*`: keep

At the target of 200 audio-hours per month, steady-state storage is under 10 GB, which fits R2's free tier.

---

## 12. Deployment

### Environments

| Environment | Where | Purpose |
|---|---|---|
| Local | Docker Compose on your PC (WSL2) | Development |
| Production | One Hetzner VM | Live site |

Stage 1 doesn't need a separate staging server. Use a staging Cloudflare Pages preview plus a `docker compose -p staging` stack on the same VM for pre-release testing if needed.

### Server

- **Hetzner CCX23** (4 dedicated vCPU, 16 GB RAM) to start, with an upgrade path to **CCX33** (8 vCPU, 32 GB). Choose a location close to most users: Falkenstein/Helsinki for Europe, Ashburn/Hillsboro for the US, Singapore for Asia.
- Ubuntu 24.04 LTS with Docker and the Compose plugin.
- Firewall: allow only 80/443 (Cloudflare IP ranges only) and SSH with keys, from your IP.
- Automatic security updates (`unattended-upgrades`).

### Containers (`server/docker-compose.yml`)

| Service | Image | Replicas | Memory limit |
|---|---|---|---|
| `caddy` | caddy:2 | 1 | 128 MB |
| `api` | app image, `uvicorn server.api.main:app --workers 2` | 1 | 512 MB |
| `worker` | app image, `arq server.worker.main.WorkerSettings` | 2 on CCX23, 4 on CCX33 | 2 GB each |
| `redis` | redis:7-alpine, AOF on | 1 | 256 MB |

### CI/CD (GitHub Actions)

1. On every pull request: lint (ruff, oxlint), unit tests, build the Docker image, and run the reference-audio tests from [§5](#5-speech-engine).
2. On merge to `main`:
   - build and push the image to GitHub Container Registry (tagged with the commit SHA)
   - Cloudflare Pages builds `web/` automatically
   - SSH to the VM, `docker compose pull && docker compose up -d`, check `/v1/health`, and roll back to the previous tag if it fails
3. Database migrations run as a separate manual workflow step.

### Secrets

Keep secrets in a `.env` file on the VM (readable only by root) and in GitHub Actions secrets: the Supabase secret key and database password, R2 keys, the Turnstile secret and the Sentry DSN. Never commit them.

---

## 13. Monitoring and operations

| What | How | Alert when |
|---|---|---|
| Site up | Better Stack / UptimeRobot checks `/v1/health` every minute | 2 failures in a row |
| Errors | Sentry (API, worker, frontend) | New issue, or error rate spike |
| Queue | Worker logs queue length and wait time every minute; a small `/v1/admin/stats` page | Average wait over 30 s for 10 min |
| Server | Hetzner graphs + `node_exporter` into Grafana Cloud (free tier) | CPU > 85% for 15 min, disk > 80% |
| Throughput | Each job logs chars, audio seconds and real-time factor (measured by the engine) | Real-time factor drops below 2× |
| Cost | Monthly check of Hetzner, R2 and Supabase dashboards | — |

**Backups:**
- Supabase handles database backups (daily on the free tier). Also run a weekly `pg_dump` to R2.
- Redis data is temporary (queue and counters), so it needs no backup.
- Audio in R2 is temporary by design.
- The server can be rebuilt from git plus `.env`; keep a short rebuild checklist in `server/README.md`.

**Runbook entries to write:** worker stuck or crashed; disk full; Redis down; abuse spike (block in Cloudflare); rolling back a release.

---

## 14. Security and privacy

- **Input limits:** check text length before queueing. Uploads accept only `.txt/.md/.docx/.pdf`, with the type confirmed from the file's content and not just its extension. Uploads are capped at 5 MB, parsed in a worker under a 20-second time limit and a memory limit, and deleted right after extraction.
- **PDF and DOCX parsing:** pypdf and python-docx run inside the worker container, which has no secrets apart from R2 and Redis access. Keep both libraries up to date (Dependabot).
- **No text retention:** don't store or log user text. Logs record lengths and settings only. This removes the main privacy risk and makes the privacy policy simple. The cache key is a hash, so the text can't be recovered from it.
- **Signed URLs:** R2 objects are private; downloads use pre-signed URLs that expire after 1 hour.
- **Auth:** verify Supabase JWTs on the API against the project's public signing keys (JWKS at `/auth/v1/.well-known/jwks.json`), checking signature, expiry and audience. The browser only ever gets the publishable key. The anonymous ID is an HMAC-signed cookie.
- **CORS:** allow only the production domain and Pages preview domains.
- **Headers:** HSTS, a CSP that allows only your own origin plus Supabase, Turnstile and Sentry.
- **Dependencies:** Dependabot for Python, npm and the Docker base image, plus a monthly rebuild.
- **Legal pages:** privacy policy (what is stored and for how long, sub-processors: Hetzner, Cloudflare, Supabase, Sentry) and terms of use (no illegal content, no impersonation, limits can change). If you target EU users, add a cookie notice; the app only uses functional cookies, so there is no consent banner for tracking.

---

## 15. Licensing

| Component | License | What it means for the web service |
|---|---|---|
| Kokoro-82M model and voices | Apache-2.0 | Commercial use allowed; credit it on the About page |
| misaki (G2P) | MIT | Commercial use allowed |
| espeak-ng (non-English phonemes) | GPL-3.0 | Running it on your own server is not distribution, so the GPL's source-sharing terms aren't triggered. If you ever publish the Docker image or ship it to customers, you must offer espeak-ng's source. Get legal advice if this matters to your business. |
| ONNX Runtime | MIT | No restrictions |
| pypdf, python-docx, FastAPI, React | BSD/MIT | No restrictions |

Some voice IDs (`af_alloy`, `af_nova`, `am_echo`, …) share names with voices from other providers. Show the display names from `engine/voices.py`, and don't suggest any connection to those providers in marketing.

---

## 16. Capacity planning

Measured with ONNX Runtime on CPU: the engine runs at **about 3.8–4.8× real time** on a 20-thread Intel i7-12700H using all threads, and at about 75% of that speed with 4 threads.

Assumptions for a 4-vCPU server worker (2 threads per worker, 2 workers):
- each worker runs at about **1.5–2.5× real time**
- the server as a whole produces about **3–5 audio-seconds per second**

| Server | Workers × threads | Total audio throughput | Audio-hours per day at 30% load |
|---|---|---|---|
| CCX23 (4 vCPU) | 2 × 2 | ~3–5× real time | ~22–36 |
| CCX33 (8 vCPU) | 4 × 2 | ~6–10× real time | ~43–72 |

At 30% load, Stage 1's target of ~200 audio-hours per month (≈ 7 per day) uses well under a third of a CCX23. The headroom covers peaks, because usage clusters in a few hours of the day.

**Benchmark before launch:** run 20 mixed jobs (short and long texts, English and Hindi) on the chosen VM with 1, 2 and 4 threads per worker. Pick the setting with the best total throughput whose time to first audio stays under 3 s. Put the results in this section.

---

## 17. Cost plan

### Monthly running costs

| Item | Service | Plan | Est. $/month |
|---|---|---|---|
| Inference + API server | Hetzner CCX23 (4 dedicated vCPU, 16 GB) | Start here | ~$30–35 |
| — upgrade if needed | Hetzner CCX33 (8 dedicated vCPU, 32 GB) | When the queue grows | ~$60–65 |
| Server backups/snapshots | Hetzner | +20% of server price | ~$6–12 |
| Frontend hosting + CDN | Cloudflare Pages | Free | $0 |
| DNS, WAF, Turnstile | Cloudflare | Free | $0 |
| Audio storage | Cloudflare R2 | ≤10 GB free, then $0.015/GB | $0–2 |
| Database + auth | Supabase | Free tier (500 MB DB, 50k MAU) | $0 |
| — if you need daily backups/no pausing | Supabase Pro | | $25 |
| Error tracking | Sentry | Developer (free) | $0 |
| Uptime checks | Better Stack / UptimeRobot | Free | $0 |
| Metrics | Grafana Cloud | Free | $0 |
| Email for sign-in links | Supabase built-in → Resend when needed | Free up to 3k/month | $0 |
| Domain | Any registrar | ~$12/year | ~$1 |
| Container registry | GitHub (GHCR) | Free for public, or included in plan | $0 |
| **Total: minimum** | CCX23, free tiers | | **~$40** |
| **Total: comfortable** | CCX33, Supabase Pro, backups | | **~$100–120** |

### One-off costs

| Item | Est. cost |
|---|---|
| Domain registration | ~$12 |
| Development time (one developer, see [§18](#18-timeline)) | 3–4 weeks |
| Legal templates for privacy policy and terms | $0–200 |

### Cost per unit at the Stage 1 target

- ~200 audio-hours ≈ 11 million characters per month
- At the minimum setup ($40), that's **about $0.20 per audio-hour, or $3.60 per million characters**, and it gets cheaper as use grows because the server is a fixed cost.
- For comparison, commercial TTS APIs charge roughly $15–100+ per million characters.

### What changes the bill

| If… | Then… |
|---|---|
| Usage grows 3–5× | Upgrade to CCX33 or add a second CCX23 (+$30–65) |
| Audio downloads become heavy | R2 has no egress fees; costs stay flat |
| Long-text streaming is heavy | Still within Hetzner's 20 TB included traffic |
| Database grows past 500 MB | Supabase Pro ($25) |
| Abuse / scraping | Tighten limits and Cloudflare rules; the fixed-price server can't run up a surprise bill (one advantage of not starting on pay-per-use GPU) |

---

## 18. Timeline

For one developer, working full time:

| Week | Phase | Deliverables |
|---|---|---|
| 1 | **Speech engine + worker** | `server/engine/` with the short first segment for streaming; reference-audio tests; Dockerfile with espeak-ng, the spaCy model and Kokoro built in; worker that runs a job from Redis and uploads MP3 to R2 |
| 1–2 | **API** | FastAPI with `/voices`, `/tts/jobs`, WebSocket streaming, cancel, `/files/extract`, `/text/clean`; arq queue; Redis rate limits and quotas; OpenAPI docs; unit tests |
| 2–3 | **Web frontend** | Studio screen: editor, voice settings, mixing, streaming player with waveform, download; file open and clean text; Studio Dark theme; mobile layout |
| 3 | **Accounts** | Supabase Auth (email link + Google); history; saved pronunciations; Turnstile on anonymous use; database migrations with row-level security |
| 3–4 | **Production** | Hetzner VM; Caddy; Cloudflare DNS/WAF; CI/CD with automatic rollback; Sentry; uptime checks; R2 lifecycle rules; capacity benchmark ([§16](#16-capacity-planning)); privacy policy, terms, About page |
| 4+ | **Private beta** | 20–50 invited users for a week; fix issues; tune limits; then public launch |

Part time (about 15 hours a week), expect 8–10 weeks.

---

## 19. Testing and launch checklist

### Automated tests

- [ ] Unit: request validation, limit checks, cache key, PCM16 conversion, MP3 encoding
- [ ] Engine: one short sentence in each of the 7 languages produces non-empty audio
- [ ] Reference audio: engine output matches the stored clips (spectral correlation ≥ 0.997)
- [ ] Integration: create job → WebSocket receives chunks → `done` URL downloads a valid MP3
- [ ] Cancel: a cancelled long job stops within 2 s and frees the worker
- [ ] Limits: going over the per-request, daily and per-minute limits returns the right error codes
- [ ] Files: valid and damaged `.docx/.pdf`, password-protected PDF, scanned PDF without text, 5 MB+ file
- [ ] Load: 20 concurrent users for 10 minutes (k6 or Locust); no errors, first-audio p95 under 5 s

### Before launch

- [ ] Capacity benchmark recorded in [§16](#16-capacity-planning)
- [ ] Health check, Sentry alerts and uptime alerts tested by breaking something on purpose
- [ ] Rollback tested once
- [ ] R2 lifecycle rules active; signed URLs expire
- [ ] No user text in logs (check a day of logs)
- [ ] Firewall allows only Cloudflare on 80/443
- [ ] Privacy policy, terms and About page with Kokoro credit are live
- [ ] Runbook written ([§13](#13-monitoring-and-operations))

---

## 20. When to move to Stage 2

Plan Stage 2 (GPU workers, managed database, two or more API instances) when **any** of these holds for two weeks or more:

| Signal | Threshold |
|---|---|
| Average queue wait at peak | over 30 s, even on CCX33 |
| Server CPU | over 70% for the busiest 4 hours of the day |
| Generated audio | over ~1,500 audio-hours per month |
| Users | over ~3,000 monthly active, or a paid plan launched |
| Uptime needs | paying users need more than one server |

Because workers only share Redis, Postgres and R2 with the rest of the system, Stage 2 is mostly adding a GPU worker type (ONNX Runtime with the CUDA provider) that reads from the same queue. The API and frontend don't change.

---

## 21. Risks and open questions

| Risk | Impact | Mitigation |
|---|---|---|
| CPU too slow for good time-to-first-audio | Users wait | Small first segment; benchmark before choosing the server; move to GPU early if needed |
| Anonymous abuse / scraping | Queue full, real users wait | Turnstile, low anonymous limits, Cloudflare rules, `busy` responses for anonymous users first |
| Single server goes down | Site down | Accept for the MVP; fast rebuild from git; uptime alerts |
| Supabase free tier pauses after a week without activity | Sign-in breaks | Regular traffic prevents it in practice; upgrade to Pro ($25) at launch if unsure |
| Crowded market | Few users | Focus on what's different: document import, text cleanup, pronunciations, voice mixing, Hindi |
| espeak-ng GPL | Legal question if the image is ever distributed | Keep the image private; get advice before distributing |

### Open questions

1. **Domain and product name** for the web version.
2. **Main audience region** (decides the server location).
3. **Anonymous use**: allow it at launch, or require sign-in from day one? Requiring sign-in makes abuse much easier to control.
4. **Is a paid plan expected soon?** If yes, design the `tier` field and limits config with paid tiers in mind now.
