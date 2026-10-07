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
