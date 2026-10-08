# Security Policy

## Supported versions

The project is in development and has no releases yet. Security fixes go to the `main` branch, which is what the live service runs.

| Version | Supported |
|---|---|
| `main` | Yes |
| Anything else | No |

## Reporting a vulnerability

**Please don't open a public issue for security problems.**

Report privately through GitHub: go to the repository's **Security** tab and choose **Report a vulnerability** ([direct link](https://github.com/Mohanavadivelu/web-text-to-speech/security/advisories/new)).

Include as much of this as you can:
- what the problem is and what an attacker could do with it
- the affected endpoint, page or file
- steps to reproduce, or a proof of concept
- any logs, screenshots or request/response pairs (remove anything personal)

### What to expect

| Step | Target time |
|---|---|
| Acknowledgement of your report | within 3 working days |
| First assessment (confirmed or not, and severity) | within 7 days |
| Fix for critical and high issues | within 14 days of confirmation |
| Fix for medium and low issues | in a following release |

We'll keep you updated, tell you when it's fixed, and credit you in the advisory and changelog if you'd like.

## Scope

**In scope:**
- the web app and its API (`/v1/*`, including the WebSocket stream)
- the job workers and document parsing (`.txt`, `.md`, `.docx`, `.pdf`)
- authentication, account data, limits and signed download links
- the configuration and code in this repository

**Out of scope:**
- denial-of-service or load testing against the live service
- spam, social engineering or physical attacks
- vulnerabilities in third-party services (Cloudflare, Supabase, Hetzner); report those to the provider
- reports from automated scanners without a demonstrated impact
- missing security headers or best-practice suggestions with no concrete exploit (still welcome as normal issues)

## Testing guidelines

When researching a vulnerability:
- only use accounts you created, and never access or change other users' data
- stay within the normal usage limits; don't run automated scans or high-volume requests against the live service
- stop and report as soon as you have confirmed the issue
- give us reasonable time to fix it before any public disclosure

We won't take legal action against research that follows these guidelines in good faith.

## How the service protects users

- **No text retention:** the text you convert is never stored in the database or written to logs. Only its length and the voice settings are recorded.
- **Short-lived audio:** generated audio is deleted automatically: after 1 day for anonymous use and 7 days for signed-in users. Download links are signed and expire after 1 hour.
- **Private storage:** audio files are not publicly listable; each one can only be reached through its signed link.
- **Uploaded documents** are checked by content type and size, parsed in an isolated worker with a time and memory limit, and deleted right after the text is extracted.
- **Authentication** uses Supabase (email link; Google later). The API verifies every token against Supabase's public signing keys, refuses invalid ones, and never accepts tokens in URLs. Each user can only read their own data (Postgres row-level security, covered by automated tests).
- **Abuse protection:** per-user and per-IP rate limits, daily quotas, Cloudflare Turnstile for anonymous use, and Cloudflare WAF rules.
- **Transport:** HTTPS only, with HSTS and a restrictive Content Security Policy.
- **Infrastructure:** the server only accepts web traffic from Cloudflare, SSH uses keys only, and security updates install automatically.

## For contributors

- Never commit secrets. Configuration comes from environment variables; `.env` files are git-ignored and `.env.example` holds placeholders only.
- Keep dependencies up to date; Dependabot opens update pull requests for Python, npm and the Docker base image.
- Never log request text or document contents. Log lengths, settings and IDs instead.
- Validate all input at the API boundary (`server/api/schemas.py`), even if the frontend already checks it.
