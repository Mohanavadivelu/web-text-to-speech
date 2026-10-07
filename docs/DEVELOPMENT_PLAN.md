# Development Plan: Stage 1

This is the build plan for the Stage 1 MVP described in [WEB_STAGE1_PLAN.md](WEB_STAGE1_PLAN.md). It breaks the work into milestones and tasks. Each task says what to build and how to tell it's done.

> **Estimates** are working days for one developer. The total is about 20 days (4 weeks full time, 8–10 weeks part time). Sections like "§8" refer to the Stage 1 plan.

---

## Contents

1. [How we work](#1-how-we-work)
2. [Milestones at a glance](#2-milestones-at-a-glance)
3. [M0: Project setup](#m0-project-setup)
4. [M1: Speech engine](#m1-speech-engine)
5. [M2: Worker and Docker image](#m2-worker-and-docker-image)
6. [M3: API](#m3-api)
7. [M4: Web frontend](#m4-web-frontend)
8. [M5: Accounts and limits](#m5-accounts-and-limits)
9. [M6: Production](#m6-production)
10. [M7: Beta and launch](#m7-beta-and-launch)
11. [Critical path and parallel work](#11-critical-path-and-parallel-work)
12. [Local development setup](#12-local-development-setup)
13. [Conventions](#13-conventions)
14. [Decisions needed, and when](#14-decisions-needed-and-when)

---

## 1. How we work

- **One branch and one pull request per task** (`m3/jobs-endpoint`). Merge to `main` only when CI passes.
- **`main` is always deployable.** From M6 on, merging to `main` deploys to production.
- **Track work in GitHub:** one GitHub milestone per M-section and one issue per task, using the task IDs below (`M3.4`).
- **A task is done when:**
  - the code is merged and has tests, or a manual check written in the PR
  - CI is green
  - anything a later task depends on (env vars, endpoints, message formats) is written down in the PR or the docs
- **The engine (`server/engine/`) never imports web code.** It must stay usable on its own from tests and scripts.

---

## 2. Milestones at a glance

| Milestone | Goal | Days | Result you can see |
|---|---|---|---|
| **M0** Project setup | Tooling, CI, accounts | 1.5 | Empty app skeleton passes CI |
| **M1** Speech engine | Kokoro engine package with streaming callbacks | 2.5 | `pytest` makes speech in all 7 languages in a Linux container |
| **M2** Worker + Docker | Jobs from Redis become MP3s in R2 | 2.75 | Queue a job by script and get an MP3 link |
| **M3** API | Full Stage 1 API with streaming | 4 | Generate and stream speech using only `curl` and a WebSocket client |
| **M4** Frontend | Studio screen in the browser | 5 | Type text, hear it within ~3 s, download it |
| **M5** Accounts + limits | Sign-in, history, pronunciations, abuse protection | 2.5 | Anonymous and signed-in limits work |
| **M6** Production | Live on the internet with monitoring | 2.5 | Public URL, alerts, automatic deploys |
| **M7** Beta + launch | Real users, fixes, launch | 5+ | Public launch |

---

## M0: Project setup

| ID | Task | Est. | Done when |
|---|---|---|---|
| M0.1 | Create the folder layout from §6 (`server/engine/`, `server/api/`, `server/worker/`, `web/`, `scripts/`, `.github/`), plus `.gitignore`, `.editorconfig` and `.env.example` | 0.25 | Structure matches §6 |
| M0.2 | Python tooling: Python 3.12, `server/requirements.txt` + `requirements-dev.txt` (pytest, ruff, httpx2), `pyproject.toml` with ruff and pytest settings | 0.25 | `ruff check` and `pytest` run (with no tests yet) |
| M0.3 | Frontend tooling: Vite + React + TypeScript in `web/`, oxlint, Prettier, Vitest | 0.25 | `npm run build` and `npm test` pass |
| M0.4 | CI workflow: on each PR run ruff + pytest + oxlint + Prettier + tsc + vitest + build, and a Docker build with a health check (no push); Dependabot for pip, npm, Docker and Actions | 0.25 | A test PR shows all checks green |
| M0.5 | Create the accounts: Cloudflare (domain, Pages, R2, Turnstile), Supabase project, Sentry, Hetzner. Write the keys only into a password manager and `.env` locally | 0.5 | Every key in `.env.example` has a real value locally |

**Needs before starting:** the domain and product name ([§14](#14-decisions-needed-and-when)).

---

## M1: Speech engine

Builds `server/engine/` as described in §5 of the Stage 1 plan.

| ID | Task | Est. | Done when |
|---|---|---|---|
| M1.1 | `engine/model_store.py`: model and voice files from Hugging Face at pinned revisions, SHA-256 check, a CLI the Docker build calls | 0.25 | A second run downloads nothing; a corrupted file is detected and fetched again |
| M1.2 | `engine/voices.py`: 7 languages, 37 voices with grades and defaults; load style tables; blend two voices | 0.25 | Unit tests: every voice belongs to one language; blending at 0% equals the base voice |
| M1.3 | `engine/g2p.py`: misaki for US/UK English, espeak-ng for the other five languages, set up once per language | 0.25 | One sentence per language becomes phonemes on Linux |
| M1.4 | `engine/synth.py`: `KokoroEngine` with ONNX Runtime session (threads from an env var), segmenting with `first_segment_chars`, phoneme packing up to 510, speed, pitch, `on_chunk` / `on_progress` callbacks, cancel through `RunOptions.terminate`, measured real-time factor | 1.0 | With `first_segment_chars=150` the first chunk is ≤150 chars of text; joining all segments gives back the input; cancel stops within 1 s |
| M1.5 | `engine/text.py`: `clean_text`, `count_words`, `estimate_seconds`, `apply_pronunciations` (plain and phoneme forms), `extract_text` for `.txt/.md/.docx/.pdf` | 0.25 | Unit tests for each function, including password-protected and image-only PDFs |
| M1.6 | `engine/audio.py`: float32 → PCM16 bytes; MP3 (64 kbps mono) and WAV with `soundfile` | 0.1 | Lengths and sample rate correct; the MP3 plays in a browser |
| M1.7 | Reference-audio tests: record one clip per language once, then compare every run with spectral correlation ≥ 0.997. Runs in CI in `python:3.12-slim` with `espeak-ng` installed | 0.4 | Test passes in CI; a deliberately changed speed fails it |

**Risk to watch:** espeak-ng and misaki setup on Linux (system libraries, the spaCy model). M1.3 and M1.7 surface this on day one, before anything is built on top.

---

## M2: Worker and Docker image

| ID | Task | Est. | Done when |
|---|---|---|---|
| M2.1 | `server/Dockerfile` (multi-stage): system packages (`espeak-ng`, `libsndfile1`), Python deps, spaCy model, then the `model_store` CLI downloads the model into `/app/models`. A non-root user. Two entry commands (`api`, `worker`) | 0.75 | Image under ~1.8 GB; the container starts with networking off and generates speech |
| M2.2 | `server/docker-compose.yml` for local development: `redis`, `api`, `worker` (Caddy comes in M6). Source mounted for hot reload | 0.25 | `docker compose up` starts all services |
| M2.3 | `worker/storage.py`: upload to R2 (boto3, S3-compatible endpoint), create 1-hour signed URLs, store keys under `audio/users/…` and `audio/anon/…` | 0.25 | Integration test against a test bucket |
| M2.4 | `worker/jobs.py` + `worker/main.py`: arq worker loads `KokoroEngine` once at startup. Each job calls `generate(..., on_chunk, on_progress, cancel_event, first_segment_chars=150)`, publishes events to `job:{id}` in Redis (message formats in §7), keeps chunks in a replay list (10-minute expiry), uploads the MP3 at the end and sends `done` | 1.0 | A script queues a job and receives `started`, chunks, `progress` and `done` with a working URL |
| M2.5 | Cancel and timeout: a thread watches `cancel:{id}` and sets `cancel_event`; jobs are killed after `max(60 s, 3 × estimate)` | 0.25 | A long job stops within 2 s of cancel; the worker picks up the next job |
| M2.6 | Local benchmark script: N parallel jobs with configurable workers × threads; prints throughput and time to first audio | 0.25 | Numbers recorded in the PR (production numbers come in M6.8) |

---

## M3: API

| ID | Task | Est. | Done when |
|---|---|---|---|
| M3.1 | FastAPI skeleton: settings from env (pydantic-settings), the shared error format from §7, request IDs in logs, Sentry, CORS, `/v1/health` (checks Redis and a worker heartbeat) | 0.5 | `/v1/health` reports OK with compose running and an error when the worker is stopped |
| M3.2 | `GET /v1/voices` from `core.voices` | 0.25 | Returns 7 languages and 37 voices with grades and defaults |
| M3.3 | `schemas.py`: Pydantic models for job requests and validation rules (voice belongs to language, ranges for speed, pitch and blend) | 0.25 | Tests for each rule |
| M3.4 | `POST /v1/tts/jobs`, `GET /v1/tts/jobs/{id}` and `DELETE /v1/tts/jobs/{id}`. Jobs are kept in Redis for now; they move to Postgres in M5.3 | 0.75 | Create, poll and cancel work end to end |
| M3.5 | `WS /v1/tts/jobs/{id}/stream`: replay buffered chunks, then follow the Redis channel live; close on `done`, `error` or `cancelled`; handle client disconnects | 0.75 | A test client gets the full audio even when it connects 2 s late |
| M3.6 | Result cache: cache key from §8; on a hit, return `done` straight away with the existing R2 object | 0.25 | The second identical request finishes in under 200 ms without reaching a worker |
| M3.7 | `POST /v1/files/extract`: check the type from file content, size limit, parse in the worker with a 20 s timeout using `engine.text.extract_text`, delete the temp file | 0.5 | Tests for good, damaged, password-protected and scanned PDFs, a good DOCX and an oversized file |
| M3.8 | `POST /v1/text/clean` | 0.1 | Output matches `engine.text.clean_text` |
| M3.9 | Basic rate limit (per IP, in Redis); the full limits come in M5 | 0.25 | 11th request in a minute gets `rate_limited` |
| M3.10 | OpenAPI export: CI writes `openapi.json`; the frontend generates its typed client from it | 0.25 | `web/src/api/` is generated, not hand-written |

**Ready for the frontend when:** M3.2, M3.4 and M3.5 are merged. M4 can start once those three are done.

---

## M4: Web frontend

| ID | Task | Est. | Done when |
|---|---|---|---|
| M4.1 | Theme: `tokens.css` with the colour, type, spacing and radius tokens from `DESIGN.md` §1–4, dark and light | 0.25 | No hard-coded colours outside `tokens.css`; theme follows the system setting |
| M4.2 | App shell and routing: Studio, History, Sign in, About, Privacy, Terms; wide-screen and mobile layouts | 0.5 | Works from 360 px wide up to large monitors, no horizontal scrolling |
| M4.3 | Text editor: word count, estimated duration (TypeScript port of `estimate_seconds`), character limit indicator, draft saved in `localStorage`, select a part of the text to speak only that part | 0.75 | Matches `engine.text.estimate_seconds` within 5% for the test texts |
| M4.4 | Voice settings panel: language, voice (with grades), mix voice + ratio, speed, pitch; remembered between visits | 0.75 | All settings reach the API; invalid combinations aren't possible in the UI |
| M4.5 | Voice previews: a build script generates one short sample per voice through the API, uploads them to R2 `previews/`; a play button next to each voice | 0.25 | Previews play instantly and create no jobs |
| M4.6 | **Streaming player:** WebSocket client plus Web Audio scheduling of PCM16 chunks at 24 kHz; switch to the MP3 for seeking when `done` arrives; play, pause, seek, download | 1.25 | Audio starts in under 3 s locally with no gaps or clicks between chunks |
| M4.7 | Waveform display of the generated audio (`DESIGN.md` §8) | 0.5 | Shows during and after generation; clicking seeks |
| M4.8 | Progress, cancel and error states, plus toast messages, following the states table in `DESIGN.md` | 0.25 | Each API error code shows a clear message |
| M4.9 | Open file (button and drag and drop) → `/files/extract`; Clean text button | 0.25 | PDF text arrives already cleaned |
| M4.10 | Playwright end-to-end test: type → generate → hear audio → download | 0.25 | Runs in CI against the compose stack |

---

## M5: Accounts and limits

| ID | Task | Est. | Done when |
|---|---|---|---|
| M5.1 | Database migrations in `supabase/migrations/` from §10 (`profiles`, `jobs`, `pronunciations`, `usage_daily`) with row-level security | 0.5 | Migrations apply to a fresh Supabase project; RLS tests pass |
| M5.2 | Auth: Supabase sign-in (email link + Google) in the frontend; the API verifies the JWT; the anonymous ID is an HMAC-signed cookie | 0.5 | Signed-in and anonymous requests are both identified correctly; a forged cookie is rejected |
| M5.3 | Job records in Postgres (settings and lengths only, **never the text**) | 0.25 | Logs and the database contain no user text (checked by a test) |
| M5.4 | Full limits from §10: per-request characters, characters per day, running/queued jobs, requests per minute; values in config; `GET /v1/me/usage` | 0.5 | Tests for each limit and tier |
| M5.5 | Turnstile on anonymous job creation and on sign-up | 0.25 | Requests without a token are rejected |
| M5.6 | History page (7 days, fresh signed URLs) and pronunciations editor (`GET/PUT /v1/me/pronunciations`, applied with `engine.text.apply_pronunciations` in the worker) | 0.5 | A saved pronunciation changes the audio |

---

## M6: Production

| ID | Task | Est. | Done when |
|---|---|---|---|
| M6.1 | Hetzner VM (CCX23): Ubuntu 24.04, Docker, SSH keys only, `unattended-upgrades`, firewall allowing 80/443 only from Cloudflare IPs | 0.5 | Server reachable only through Cloudflare |
| M6.2 | Caddy in compose for production, `docker-compose.prod.yml` with memory limits from §12, `.env` on the server | 0.25 | HTTPS works through Cloudflare |
| M6.3 | Cloudflare: DNS, Pages project for `web/`, WAF rate rule on `/v1/tts/*`, R2 lifecycle rules from §11 | 0.25 | Frontend live; lifecycle rules visible in the dashboard |
| M6.4 | Deploy workflow: build and push the image to GHCR, SSH deploy, health check, automatic rollback to the previous tag | 0.5 | A deliberately broken deploy rolls back by itself |
| M6.5 | Monitoring: Sentry in production, uptime check on `/v1/health`, `node_exporter` → Grafana Cloud, alerts from §13 | 0.25 | Each alert tested once by causing the problem |
| M6.6 | Backups: weekly `pg_dump` to R2 (GitHub Actions scheduled job) | 0.1 | One restore tested into a scratch database |
| M6.7 | About, Privacy and Terms pages (§14, §15) | 0.25 | Live, with the Kokoro credit |
| M6.8 | Production benchmark and load test (§16, §19): set workers × threads, then run 20 users for 10 minutes | 0.25 | Results written into §16 of the Stage 1 plan |
| M6.9 | Runbook in `server/README.md`: rebuild the server, roll back, stuck worker, disk full, abuse spike | 0.25 | Another person could follow it |

---

## M7: Beta and launch

| ID | Task | Est. | Done when |
|---|---|---|---|
| M7.1 | Private beta: invite 20–50 people, add a feedback link in the app | 5 days of running, ~1–2 days of fixes | Feedback collected and triaged into issues |
| M7.2 | Fix critical bugs and tune limits based on the queue and usage numbers | as needed | No open critical issues |
| M7.3 | Work through the §19 launch checklist | 0.5 | Every box ticked |
| M7.4 | Public launch | Announced |
| M7.5 | Two weeks after launch: review the numbers against the Stage 2 triggers (§20) | 0.25 | Decision written down: stay, upgrade the server, or start Stage 2 |

---

## 11. Critical path and parallel work

```
M0 ─► M1 ─► M2 ─► M3.1–M3.5 ─┬─► M4 ─────────┬─► M6 ─► M7
                             ├─► M3.6–M3.10  │
                             └─► M5 ─────────┘
```

- **Critical path:** M1 → M2 → M3 (core endpoints) → M4.6 (streaming player). The streaming player is the hardest frontend piece, so start it as soon as the WebSocket endpoint works.
- **Can start early:**
  - M4.1–M4.4 (theme, layout, editor, voice panel) can be built against a mocked API while M2 and M3 are underway
  - M0.5 (accounts) and M6.1 (server) are independent of code
- **With two developers:** one takes M1–M3 + M6, the other takes M4 + M5 (frontend parts). That's about 2.5–3 weeks in total.

---

## 12. Local development setup

**Requirements:** Windows 11 with WSL2 (or macOS / Linux), Docker Desktop, Node 22+ and Python 3.11 or 3.12 (production uses 3.12).

**Daily loop:**

```bash
cp .env.example .env                                  # fill in local values (M0.5)
docker compose -f server/docker-compose.yml up        # redis, api :8000, worker
cd web && npm install && npm run dev                  # frontend :5173, proxies /v1 to :8000
```

**Engine on its own** (no Docker needed for quick experiments):

```bash
python -m server.engine.model_store download          # once
python -m server.engine.synth "Hello there." --voice af_heart --out hello.wav
```

**Tests:**

```bash
pytest server/tests                                    # API and worker
cd web && npm test                                     # unit tests
npx playwright test                                    # end to end (compose must be running)
```

---

## 13. Conventions

| Area | Rule |
|---|---|
| Python | Python 3.12, ruff for linting and formatting, type hints on public functions, `logging` (no `print`) |
| TypeScript | Strict mode, oxlint + Prettier, function components and hooks, API types only from the generated client |
| API | Everything under `/v1`; error format from §7; breaking changes need `/v2` |
| Config | All settings and limits from env vars, documented in `.env.example` |
| Logs | Structured JSON with the request ID and job ID; **never log user text** |
| Commits | Short imperative subject line; reference the task ID (`M3.4: add jobs endpoint`) |
| Secrets | Never in git; `.env` locally and on the server, GitHub secrets in CI |

---

## 14. Decisions needed, and when

| Decision | Needed by | Options / recommendation |
|---|---|---|
| Product name and domain | M0.5 | — |
| Main audience region (server location) | M6.1 | Europe → Falkenstein/Helsinki; US → Ashburn; Asia/India → Singapore |
| Anonymous use at launch? | M5.4 | Recommendation: yes, with the low §10 limits and Turnstile; turn it off quickly if abused |
| Supabase free or Pro at launch | M6 | Free is enough to start; Pro ($25) once real users depend on it |
| Paid plan in the near future? | M5.1 | If yes, keep the `tier` column and config-based limits ready (already in the plan) |
| When to turn `core` into a pip package | Stage 2 | Recommendation: Stage 2, or earlier if the engine changes often |
