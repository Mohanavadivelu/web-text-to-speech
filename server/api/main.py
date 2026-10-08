"""FastAPI application: routes, error format, CORS, request IDs and error tracking.

uvicorn server.api.main:app
"""

from __future__ import annotations

import logging
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from server.api import errors, routes_me, routes_meta, routes_text, routes_tts
from server.api.auth import TokenVerifier
from server.api.deps import ArqJobQueue, Services, Turnstile
from server.config import Settings, get_settings

log = logging.getLogger("server.api")


def _init_sentry(settings: Settings) -> None:
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        send_default_pii=False,  # never send request bodies (user text) or cookies
        traces_sample_rate=0.0,
    )


async def _real_services(settings: Settings) -> Services:
    import redis.asyncio as aioredis
    from arq import create_pool
    from arq.connections import RedisSettings

    from server.db import PostgresDatabase
    from server.worker.storage import Storage

    return Services(
        settings=settings,
        redis=aioredis.from_url(settings.redis_url),
        queue=ArqJobQueue(await create_pool(RedisSettings.from_dsn(settings.redis_url))),
        storage=Storage(settings),
        db=await PostgresDatabase.connect(settings.database_url),
        verifier=TokenVerifier(settings),
        bots=Turnstile(settings.turnstile_secret_key),
    )


def create_app(services: Services | None = None) -> FastAPI:
    """The app; tests pass fake services, otherwise real ones are made at startup."""
    settings = services.settings if services else get_settings()
    logging.basicConfig(
        level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    _init_sentry(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        own = services is None
        app.state.services = services or await _real_services(settings)
        yield
        if own:
            await app.state.services.queue.close()
            await app.state.services.redis.aclose()
            await app.state.services.db.close()

    app = FastAPI(
        title="Kokoro TTS Web API",
        version="0.1.0",
        description="Text-to-speech jobs with live streaming. Errors always look like "
        '`{"error": {"code": ..., "message": ...}}`.',
        lifespan=lifespan,
    )
    errors.install(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.public_web_origin.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )

    @app.middleware("http")
    async def request_id_and_log(request: Request, call_next):
        request_id = request.headers.get("x-request-id", "")[:64] or secrets.token_hex(8)
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        # Method, path and status only: never the body, which holds the user's text
        log.info(
            "%s %s %d %.0fms [%s]",
            request.method, request.url.path, response.status_code,
            (time.perf_counter() - started) * 1000, request_id,
        )  # fmt: skip
        return response

    for module in (routes_meta, routes_tts, routes_text, routes_me):
        app.include_router(module.router)
    return app


app = create_app()
