"""The caller's own things: limits and usage, history, saved pronunciations."""

from __future__ import annotations

import asyncio
import datetime as dt

from fastapi import APIRouter, Depends

from server.api import limits
from server.api.auth import Caller, caller_dependency, user_dependency
from server.api.deps import Services, services
from server.api.schemas import (
    ErrorResponse,
    HistoryItem,
    HistoryOut,
    LimitsOut,
    MeOut,
    PronunciationsBody,
)

router = APIRouter(prefix="/v1/me", tags=["me"])
ERRORS = {401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}


@router.get("", response_model=MeOut)
async def me(
    caller: Caller = Depends(caller_dependency), svc: Services = Depends(services)
) -> MeOut:
    """Who you are (if signed in), your limits and today's usage. Works for everyone."""
    lim = limits.limits_for(caller, svc.settings)
    return MeOut(
        signed_in=caller.signed_in,
        email=caller.email,
        limits=LimitsOut(
            max_chars=lim.max_chars,
            daily_chars=lim.daily_chars,
            max_active_jobs=lim.max_active_jobs,
            uploads=lim.uploads,
            wav=lim.wav,
        ),
        chars_today=await limits.chars_used_today(svc.redis, caller),
    )


@router.get("/history", response_model=HistoryOut, responses=ERRORS)
async def history(
    caller: Caller = Depends(user_dependency), svc: Services = Depends(services)
) -> HistoryOut:
    """Your finished audio from the last 7 days, newest first, with fresh download links."""
    days = svc.settings.history_days
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
    rows = await svc.db.history(caller.id, since)

    async def item(row: dict) -> HistoryItem:
        def link(key: str | None) -> str | None:
            if not key:
                return None
            extension = key.rsplit(".", 1)[-1]
            return svc.storage.signed_url(key, f"kokoro-{row['id']}.{extension}")

        url, wav_url = await asyncio.gather(
            asyncio.to_thread(link, row["storage_key"]), asyncio.to_thread(link, row["wav_key"])
        )
        created = row["created_at"]
        return HistoryItem(
            id=row["id"],
            created_at=created.isoformat() if hasattr(created, "isoformat") else str(created),
            lang=row["lang"],
            voice=row["voice"],
            blend_voice=row["blend_voice"],
            blend_ratio=row["blend_ratio"],
            speed=row["speed"],
            pitch=row["pitch"],
            chars=row["chars"],
            audio_seconds=row["audio_seconds"],
            url=url,
            wav_url=wav_url,
        )

    return HistoryOut(items=await asyncio.gather(*(item(r) for r in rows)), days=days)


@router.get("/pronunciations", response_model=PronunciationsBody, responses=ERRORS)
async def get_pronunciations(
    caller: Caller = Depends(user_dependency), svc: Services = Depends(services)
) -> PronunciationsBody:
    """Your saved pronunciations, applied to every job you create."""
    return PronunciationsBody(entries=await svc.db.get_pronunciations(caller.id))


@router.put("/pronunciations", response_model=PronunciationsBody, responses=ERRORS)
async def put_pronunciations(
    body: PronunciationsBody,
    caller: Caller = Depends(user_dependency),
    svc: Services = Depends(services),
) -> PronunciationsBody:
    """Replace your saved pronunciations. "say" is a spelling, or phonemes in slashes."""
    entries = [{"word": e.word.strip(), "say": e.say.strip()} for e in body.entries]
    await svc.db.put_pronunciations(caller.id, entries)
    return PronunciationsBody(entries=entries)
