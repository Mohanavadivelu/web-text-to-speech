# Changelog

All notable changes to this project are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project will use [Semantic Versioning](https://semver.org/) from its first release.

## [Unreleased]

### Added
- Stage 1 (MVP) plan: scope, architecture, speech engine, API, limits, storage, deployment, monitoring, security, licensing, capacity and cost plan (`docs/WEB_STAGE1_PLAN.md`).
- Development plan with milestones M0–M7, task estimates and done criteria (`docs/DEVELOPMENT_PLAN.md`).
- Web UI design spec: colour, type, spacing and motion tokens, layouts for wide, medium and narrow screens, components, states, keyboard shortcuts and accessibility (`docs/DESIGN.md`).
- README, changelog and security policy.
- Project layout (`server/engine`, `server/api`, `server/worker`, `web`, `scripts`), `.gitattributes`, `.editorconfig`, `.gitignore` and `.env.example` (M0.1).
- Python tooling: `pyproject.toml` with ruff and pytest settings, pinned `server/requirements.txt` and `requirements-dev.txt`, and a first `/v1/health` endpoint with a test (M0.2).
- Web app scaffold: Vite, React 19, TypeScript (strict), oxlint, Prettier and Vitest, with a `/v1` proxy to the local API (M0.3).
- CI on GitHub Actions: Python lint and tests, web lint, format, typecheck, tests and build, and a Docker build with a health check. Dependabot for pip, npm, Docker and Actions (M0.4).
- Supabase CLI project (`supabase/config.toml`, `supabase/migrations/`) with local auth redirects for the Vite dev server; `.env.example` uses Supabase's publishable and secret keys and JWKS token verification (M0.5).
- Speech engine package `server/engine/` (M1): Kokoro-82M on ONNX Runtime with 7 languages and 37 voices, voice mixing, speed and pitch, streaming callbacks, a short first segment so streaming starts in ~2 s, and cancel in ~0.3 s. Includes text cleanup, pronunciations, duration estimates, `.txt/.md/.docx/.pdf` extraction with type and size checks, and MP3 (~64 kbps) / WAV encoding.
- Model store with every file pinned to one Hugging Face revision and verified by SHA-256, with resumable downloads and a `download` / `verify` command line.
- Engine tests: fast unit tests, model tests against reference clips for every language, and a CI job that caches the model files.
- Speech worker (M2): arq jobs that stream audio pieces and progress through Redis (replayable for late listeners), store the MP3 (and optional WAV) in R2-compatible storage, and return a 1-hour signed link; cancel, per-job timeouts, a heartbeat for health checks, and user-safe error messages.
- Production Dockerfile with the model built in (1.65 GB), and a Docker Compose stack with Redis, SeaweedFS as local S3 storage, the API and the worker.
- `scripts/try_job.py` (run a job end to end) and `scripts/benchmark.py`; CI starts the whole stack and runs a real job on every push.
- API (M3): create, check and cancel speech jobs; a WebSocket that streams status and audio (in frames of up to 1 s) and replays everything to late listeners; voices; text cleanup; document upload parsed in an isolated, time- and memory-limited process; result cache with server-side copies; one error format; request IDs; Sentry (no user text sent).
- Separate short and long job queues, with the long worker at lower CPU priority and ONNX thread spinning off: a short request's first audio stays around 3.5 s while long jobs run (was ~140 s).
- Anonymous visitors get an HMAC-signed cookie; jobs are visible only to their owner. Limits: text length, active jobs per visitor, requests per minute per IP and queue length.
- OpenAPI schema exported to `web/src/api/openapi.json` with generated TypeScript types; CI fails if either is out of date.

- Web Studio (M4): text editor with counts, limit meter, file open (button or drag and drop) and Clean text with Undo; voice settings with previews, mixing, speed and pitch; a streaming player that starts within ~1.5 s, buffers without gaps and seeks within what has arrived; a live waveform; download; toasts; dark and light themes; layouts for desktop, tablet (drawer) and phone (bottom sheet); keyboard shortcuts and screen-reader announcements.
- Voice preview clips for all 37 voices, served as static files (`scripts/make_voice_previews.py`).
- `GET /v1/config` (the visitor's limits) and download links that save as `kokoro-<job>.mp3`.
- Browser tests (Playwright) for desktop and phone, run in CI against the Docker stack, plus unit tests for the streaming player.

- Renamed to **Narravo**; the top bar shows "Narravo Studio" and no page links (History and About moved to the side panel and the account menu). Download files are named `narravo-<job>.mp3`.
- Studio redesign: Settings | History tabs in the side panel; the voice as a card that opens a voice picker (search, language and gender filters, sort, preview every voice, mixing); exact number boxes next to Speed and Pitch; a reading font in the editor with the tools along the bottom; on phones and tablets, voice, settings and history buttons right above Generate.
- The player bar stays on every page and keeps playing while you move between Studio, History and About; playing an item from History loads it into the same player. Pitch is always visible (no "Advanced" section).
- Accounts (M5), on local Supabase in development: email-link sign-in; signed-in limits (20,000 characters per request, 100,000 a day, 3 active jobs, 30 requests a minute per account) and anonymous limits (2,000 / 10,000 / 2 / 10 per IP); a usage meter; WAV downloads, document uploads, a 7-day History page and saved pronunciations for signed-in users.
- Database schema (`supabase/migrations`) with row-level security: users read only their own jobs, pronunciations and profile; nobody reads usage statistics. Job text is never stored.
- `GET /v1/me`, `GET /v1/me/history`, `GET/PUT /v1/me/pronunciations`.
- Database tests against real Postgres in CI, and browser tests for sign-in, History, pronunciations and sign-out.

### Security
- Supabase tokens are verified by the API against the project's public keys (signature, expiry, audience, issuer); an invalid token is refused, never treated as anonymous. WebSockets carry the token as a subprotocol so it never appears in URLs or logs.
- Anonymous job creation requires Cloudflare Turnstile; the API refuses to start in production without a Turnstile secret.
- The API refuses to start in production with the development cookie secret, and only trusts `CF-Connecting-IP` when configured to (it's spoofable without Cloudflare in front).
