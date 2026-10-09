# One image for the API and the workers, with the speech model built in.
# Build from the repository root:  docker build -f server/Dockerfile .
#
#   API:     uvicorn server.api.main:app --host 0.0.0.0 --port 8000   (default)
#   Worker:  arq server.worker.main.WorkerSettings

# ── 1. Python dependencies in a virtual environment ──────────────────────────
FROM python:3.12-slim AS deps

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY server/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# ── 2. Model files, downloaded and verified (cached until model_store.py changes) ─
FROM deps AS models

WORKDIR /build
COPY server/__init__.py server/__init__.py
COPY server/engines/__init__.py server/engines/
COPY server/engines/kokoro/__init__.py server/engines/kokoro/model_store.py server/engines/kokoro/
RUN python -m server.engines.kokoro.model_store download --dir /models

# ── 3. Runtime image ─────────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    MODELS_DIR=/app/models

RUN useradd --create-home --uid 10001 app
WORKDIR /app

COPY --from=deps /opt/venv /opt/venv
COPY --from=models /models /app/models
COPY server/ server/

USER app
EXPOSE 8000
CMD ["uvicorn", "server.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
