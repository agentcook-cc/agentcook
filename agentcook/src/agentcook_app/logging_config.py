"""Structured logging via structlog with per-request correlation.

A ``request_id`` is generated for every HTTP request and bound to
``structlog.contextvars`` so every log line emitted while handling that
request carries it. This is the minimum we need before OpenTelemetry
lands in Phase 2 (ADR-005).
"""

from __future__ import annotations

import logging
import uuid

import structlog
from fastapi import FastAPI, Request


def configure(level: str = "INFO") -> None:
    """Set up structlog + stdlib logging to emit JSON-friendly key/value lines."""
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.KeyValueRenderer(
                key_order=("timestamp", "level", "event", "request_id")
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level, logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def install_request_context(app: FastAPI) -> None:
    """Bind a fresh ``request_id`` into structlog contextvars per request."""
    log = structlog.get_logger()

    @app.middleware("http")
    async def _request_id_middleware(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(
            request_id=rid,
            method=request.method,
            path=request.url.path,
        )
        try:
            log.info("request.start")
            response = await call_next(request)
            log.info("request.end", status=response.status_code)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            structlog.contextvars.clear_contextvars()


__all__ = ["configure", "install_request_context"]
