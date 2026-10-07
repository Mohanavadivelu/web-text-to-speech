"""Health check and the voice catalogue."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from server.api.deps import Services, services
from server.api.schemas import HealthOut, LanguageOut, VoiceOut, VoicesResponse
from server.engine import voices
from server.events import WORKER_HEARTBEAT_PREFIX

router = APIRouter(prefix="/v1", tags=["meta"])


@router.get("/health", response_model=HealthOut, responses={503: {"model": HealthOut}})
async def health(svc: Services = Depends(services)):
    """OK when Redis answers and at least one speech worker is alive."""
    try:
        await svc.redis.ping()
        workers = len([k async for k in svc.redis.scan_iter(match=WORKER_HEARTBEAT_PREFIX + "*")])
        redis_state = "ok"
    except Exception:
        workers, redis_state = 0, "down"
    ok = redis_state == "ok" and workers > 0
    body = HealthOut(status="ok" if ok else "degraded", redis=redis_state, workers=workers)
    return JSONResponse(body.model_dump(), status_code=200 if ok else 503)


_VOICES = VoicesResponse(
    languages=[
        LanguageOut(
            code=lang.code,
            name=lang.name,
            default_voice=voices.default_voice(lang.code).id,
            preview_text=lang.preview_text,
            voices=[
                VoiceOut(id=v.id, name=v.name, gender=v.gender, grade=v.grade)
                for v in voices.voices_for(lang.code)
            ],
        )
        for lang in voices.LANGUAGES.values()
    ]
)


@router.get("/voices", response_model=VoicesResponse)
async def list_voices() -> VoicesResponse:
    """Languages and their voices (the first voice is the default), plus speed and pitch ranges."""
    return _VOICES
