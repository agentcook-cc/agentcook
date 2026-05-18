"""Canonical error envelope handling.

Wraps FastAPI's default JSON-body for HTTPException into the flat
``{code, message, detail}`` shape B's frontend expects (§7.6). Endpoints
raise ``HTTPException(detail=ErrorEnvelope(...).model_dump())`` and the
handler below normalizes any default-shape error too.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from agentcook_app.schemas import ErrorEnvelope

logger = logging.getLogger(__name__)


def _envelope_response(status_code: int, code: str, message: str, detail=None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorEnvelope(code=code, message=message, detail=detail).model_dump(),
    )


async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    # If the endpoint already produced an envelope dict, pass through.
    if isinstance(exc.detail, dict) and {"code", "message"} <= exc.detail.keys():
        return JSONResponse(status_code=exc.status_code, content=exc.detail, headers=exc.headers)
    return _envelope_response(
        status_code=exc.status_code,
        code=f"HTTP_{exc.status_code}",
        message=str(exc.detail) if exc.detail else "HTTP error",
    )


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _envelope_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="INVALID_INPUT",
        message="Request validation failed.",
        detail={"errors": exc.errors()},
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception serving %s %s", request.method, request.url.path)
    return _envelope_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_ERROR",
        message="An internal error occurred.",
    )


def install(app: FastAPI) -> None:
    """Register exception handlers.

    Both FastAPI's ``HTTPException`` and the underlying Starlette
    ``HTTPException`` are registered so the body-parse 400 path (raised
    deep in Starlette's request reader) also returns the canonical
    envelope rather than ``{"detail": "..."}``.
    """
    app.add_exception_handler(HTTPException, _http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)


__all__ = ["install"]
