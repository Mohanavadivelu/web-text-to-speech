"""Text helpers: clean pasted text, and extract text from uploaded documents."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, UploadFile

from server.api import limits
from server.api.auth import Caller, caller_dependency, set_cookie
from server.api.deps import Services, services
from server.api.errors import APIError
from server.api.isolation import extract_isolated
from server.api.schemas import ErrorResponse, ExtractOut, TextIn, TextOut
from server.engines.common.text import ExtractError, clean_text

router = APIRouter(prefix="/v1", tags=["text"])
ERRORS = {code: {"model": ErrorResponse} for code in (401, 413, 422, 429)}


@router.post("/text/clean", response_model=TextOut, responses=ERRORS)
async def clean(body: TextIn) -> TextOut:
    """Fix pasted text: quotes, links, markdown symbols, lines broken mid-sentence."""
    return TextOut(text=clean_text(body.text))


@router.post("/files/extract", response_model=ExtractOut, responses=ERRORS)
async def extract(
    file: UploadFile,
    response: Response,
    caller: Caller = Depends(caller_dependency),
    svc: Services = Depends(services),
) -> ExtractOut:
    """Text from a .txt, .md, .docx or .pdf file (up to 5 MB; signed-in users).

    PDF text comes back cleaned."""
    settings = svc.settings
    lim = limits.limits_for(caller, settings)
    await limits.check_rate(svc.redis, caller, lim, bucket="files")
    if not lim.uploads:
        raise APIError("unauthorized", "Sign in to open documents.")
    set_cookie(response, caller, secure=settings.app_env == "production")

    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise APIError("too_long", f"Files can be up to {settings.max_upload_bytes // 2**20} MB.")
    try:
        text, cleaned = await extract_isolated(
            data, file.filename or "upload", settings.extract_timeout_seconds
        )
    except ExtractError as exc:
        raise APIError("invalid_input", str(exc)) from None
    return ExtractOut(text=text, cleaned=cleaned, characters=len(text))
