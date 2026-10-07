# One image for the API and the workers (the worker command arrives in M2).
# M2.1 extends this with espeak-ng, the spaCy model and the Kokoro model files.
# Build from the repository root:  docker build -f server/Dockerfile .

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY server/requirements.txt server/requirements.txt
RUN pip install -r server/requirements.txt

COPY server/ server/

RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000
CMD ["uvicorn", "server.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
