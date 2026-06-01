"""Prometheus metrics for the agentcook FastAPI runtime.

Phase 2 Day 19 — Agent C.

Exposes ``/metrics`` endpoint for Prometheus scraping and provides
a FastAPI middleware that automatically records request count and latency.

Usage in ``main.py``::

    from agentcook_app.metrics import setup_metrics
    # inside create_app():
    setup_metrics(app)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

_PROM_AVAILABLE = False

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    _PROM_AVAILABLE = True
except ImportError:
    pass


# ── Pre-defined metrics ─────────────────────────────────────────────────────

if _PROM_AVAILABLE:
    REQUEST_COUNT = Counter(
        "agentcook_http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
    )

    REQUEST_LATENCY = Histogram(
        "agentcook_http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "path"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )

    ACTIVE_SESSIONS = Gauge(
        "agentcook_active_sessions",
        "Number of currently active chat sessions",
    )


# ── Setup ────────────────────────────────────────────────────────────────────


def setup_metrics(app: FastAPI) -> None:
    """Wire Prometheus metrics endpoint and collection middleware into FastAPI.

    Gracefully no-ops when prometheus_client is not installed.
    """
    if not _PROM_AVAILABLE:
        import logging

        logging.getLogger(__name__).info(
            "prometheus_client not installed — metrics disabled. "
            "Install with: uv pip install prometheus-client"
        )
        return

    from starlette.requests import Request
    from starlette.responses import Response

    @app.get("/metrics", tags=["meta"], include_in_schema=False)
    async def metrics_endpoint() -> Response:
        body = generate_latest()
        return Response(
            content=body,
            media_type=CONTENT_TYPE_LATEST,
            headers={"Content-Length": str(len(body))},
        )

    @app.middleware("http")
    async def prometheus_middleware(request: Request, call_next):  # noqa: ANN001
        # Skip metrics endpoint itself to avoid self-referential noise.
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        path = request.url.path

        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        status = str(response.status_code)
        REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
        REQUEST_LATENCY.labels(method=method, path=path).observe(elapsed)

        return response
