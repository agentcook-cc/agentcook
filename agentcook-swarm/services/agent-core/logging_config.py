"""Structured JSON logging via structlog — shared by agent-core + connector.

Every log line is one JSON object with these fields:

- ``timestamp``       ISO-8601 UTC
- ``level``           debug / info / warning / error / critical
- ``service``         from ``OTEL_SERVICE_NAME`` env var
- ``message``         the actual log event name (e.g. ``request.start``)
- ``trace_id`` / ``span_id``     injected by OTel ``LoggingInstrumentor``
                                 when a span is active
- ``correlation_id``  injected from the ``X-Correlation-Id`` HTTP header
                      via :func:`bind_correlation_id`
- plus any per-call ``extra`` key/values

Promtail then scrapes container stdout, the JSON survives unchanged
into Loki, and Grafana's "Explore" view supports field-aware filtering
(``service = "agent-core"`` AND ``level = "error"`` etc).

Usage at service startup::

    from logging_config import configure_logging
    configure_logging()
    log = structlog.get_logger()
    log.info("service.started", port=8000)

Inside a FastAPI middleware to bind correlation id::

    from logging_config import bind_correlation_id
    bind_correlation_id(request.headers.get("X-Correlation-Id"))
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import structlog


DEFAULT_LEVEL = "INFO"
SERVICE_ENV = "OTEL_SERVICE_NAME"
CORRELATION_HEADER = "X-Correlation-Id"


def _add_service_name(_logger, _method, event_dict):
    """structlog processor: tag every line with the service name."""
    event_dict.setdefault("service", os.getenv(SERVICE_ENV, "unknown"))
    return event_dict


def configure_logging(level: str | None = None) -> None:
    """Configure structlog + stdlib logging to emit JSON lines.

    Idempotent — call once at service startup. Falls back to plain
    logging if structlog isn't installed (so unit tests in the swarm
    repo don't require the dep at collection time).
    """
    try:
        import structlog
    except ImportError:
        logging.basicConfig(
            level=level or os.getenv("LOG_LEVEL", DEFAULT_LEVEL),
            format="%(asctime)s %(name)s %(levelname)s %(message)s",
        )
        logging.getLogger(__name__).warning("structlog not installed — falling back to stdlib")
        return

    log_level = level or os.getenv("LOG_LEVEL", DEFAULT_LEVEL)

    # Stdlib root logger: write to stdout (Promtail tails this).
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    structlog.configure(
        processors=[
            # Carry contextvars (correlation_id, request_id, etc.) into every line.
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_service_name,
            # OTel injects trace_id / span_id when a span is active; that
            # work happens in stdlib logging via LoggingInstrumentor.
            # structlog respects the resulting LogRecord attributes here:
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # Final renderer: JSON. Loki indexes the labels we attach in
            # Promtail config; the body is the raw JSON line.
            structlog.processors.JSONRenderer(sort_keys=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def bind_correlation_id(value: str | None) -> str:
    """Bind a correlation id into structlog's contextvars.

    If *value* is falsy, generates a fresh UUID4. Returns the value
    actually bound — the caller can echo it back in the response
    ``X-Correlation-Id`` header so the client can correlate.
    """
    try:
        import structlog
    except ImportError:
        return value or uuid.uuid4().hex

    cid = value or uuid.uuid4().hex
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlation_id=cid)
    return cid


def get_logger(name: str | None = None) -> object:
    """Return a structlog logger (or stdlib fallback)."""
    try:
        import structlog

        return structlog.get_logger(name) if name else structlog.get_logger()
    except ImportError:
        return logging.getLogger(name or __name__)


__all__ = [
    "CORRELATION_HEADER",
    "bind_correlation_id",
    "configure_logging",
    "get_logger",
]
