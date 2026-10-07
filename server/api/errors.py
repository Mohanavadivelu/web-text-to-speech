"""One error shape for every API response: {"error": {"code": ..., "message": ...}}."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)

STATUS = {
    "invalid_input": 422,
    "too_long": 413,
    "quota_exceeded": 429,
    "rate_limited": 429,
    "busy": 503,
    "not_found": 404,
    "internal": 500,
}


class APIError(Exception):
    def __init__(self, code: str, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after = retry_after


def error_response(code: str, message: str, retry_after: int | None = None) -> JSONResponse:
    headers = {"Retry-After": str(retry_after)} if retry_after else None
    return JSONResponse(
        {"error": {"code": code, "message": message}}, status_code=STATUS[code], headers=headers
    )


def _validation_message(exc: RequestValidationError) -> str:
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first.get("loc", ())[1:]) or "request"
    message = first.get("msg", "is invalid").removeprefix("Value error, ")
    return f"{field}: {message}"


def install(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error(_request: Request, exc: APIError):
        return error_response(exc.code, exc.message, exc.retry_after)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        return error_response("invalid_input", _validation_message(exc))

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return error_response("not_found", "Not found.")
        if exc.status_code == 405:
            return JSONResponse(
                {"error": {"code": "invalid_input", "message": "Method not allowed."}},
                status_code=405,
            )
        return error_response("internal", "Something went wrong on our side. Please try again.")

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, exc: Exception):
        log.exception("Unhandled error", exc_info=exc)
        return error_response("internal", "Something went wrong on our side. Please try again.")
