"""Structured logging via structlog with per-request correlation.

A ``request_id`` is taken from ``X-Request-ID`` (or generated) for every
HTTP request and bound to ``structlog.contextvars`` so every log line
emitted while handling that request carries it — including lines from
stdlib loggers, which are bridged into the same live log stream
(:mod:`agentcook_app.log_stream`).
"""

from __future__ import annotations

import logging
import re
import time
import uuid

import structlog
from fastapi import FastAPI, Request

from agentcook_app.log_stream import LogHubHandler, structlog_processor

_QUIET_PATHS = ("/health", "/metrics")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def configure(level: str = "INFO") -> None:
    """Set up structlog + stdlib logging; idempotent."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=numeric, format="%(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(numeric)
    if not any(isinstance(h, LogHubHandler) for h in root.handlers):
        root.addHandler(LogHubHandler(level=numeric))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog_processor,
            structlog.processors.KeyValueRenderer(
                key_order=("timestamp", "level", "event", "request_id")
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def install_request_context(app: FastAPI) -> None:
    """Bind a ``request_id`` into structlog contextvars per request."""
    log = structlog.get_logger("agentcook_app.http")

    @app.middleware("http")
    async def _request_id_middleware(request: Request, call_next):  # noqa: ANN001
        incoming = request.headers.get("X-Request-ID", "")
        rid = incoming if _REQUEST_ID.match(incoming) else uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(
            request_id=rid,
            method=request.method,
            path=request.url.path,
        )
        quiet = request.url.path.startswith(_QUIET_PATHS)
        started = time.perf_counter()
        try:
            if not quiet:
                log.info("request.start")
            response = await call_next(request)
            if not quiet:
                log.info(
                    "request.end",
                    status=response.status_code,
                    duration_ms=round((time.perf_counter() - started) * 1000, 1),
                )
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            structlog.contextvars.clear_contextvars()


__all__ = ["configure", "install_request_context"]
