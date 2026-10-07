"""FastAPI application.

M0 provides only the health check; the full skeleton (settings, error format,
Sentry, CORS, dependency checks) arrives in M3.1.
"""

from fastapi import FastAPI

app = FastAPI(title="Kokoro TTS Web API", version="0.0.0")


@app.get("/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
