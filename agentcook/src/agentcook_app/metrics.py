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

    AGENT_RUNS = Counter(
        "agentcook_agent_runs_total",
        "Agent runs by agent and outcome",
        ["agent", "outcome"],
    )
    AGENT_RUN_DURATION = Histogram(
        "agentcook_agent_run_duration_seconds",
        "Wall-clock duration of agent runs",
        ["agent"],
        buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120),
    )
    AGENT_TURNS = Histogram(
        "agentcook_agent_turns",
        "Model turns per agent run",
        ["agent"],
        buckets=(1, 2, 3, 4, 6, 8, 12, 16),
    )
    TOOL_CALLS = Counter(
        "agentcook_tool_calls_total",
        "Tool invocations by tool and outcome",
        ["tool", "outcome"],
    )
    LLM_TOKENS = Counter(
        "agentcook_llm_tokens_total",
        "LLM tokens by model and direction (input/output/cached)",
        ["model", "direction"],
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

        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        # Label by route *template* (/api/v1/sessions/{session_id}) — raw
        # paths would create one time series per session id and blow up
        # Prometheus cardinality.
        route = request.scope.get("route")
        path = getattr(route, "path", None) or "unmatched"

        status = str(response.status_code)
        REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
        REQUEST_LATENCY.labels(method=method, path=path).observe(elapsed)

        return response


# ── Agent-loop metrics (RunHooks bridge) ─────────────────────────────────────

try:
    from agentcook_core import RunHooks as _RunHooks
except ImportError:  # pragma: no cover
    _RunHooks = object  # type: ignore[assignment,misc]


class AgentMetricsHooks(_RunHooks):  # type: ignore[misc,valid-type]
    """Export agent runs, tool calls and token usage to Prometheus."""

    def __init__(self, model: str) -> None:
        self._model = model

    async def on_llm_end(self, ctx, agent, message, usage) -> None:  # noqa: ANN001
        if not _PROM_AVAILABLE:
            return
        LLM_TOKENS.labels(model=self._model, direction="input").inc(usage.input)
        LLM_TOKENS.labels(model=self._model, direction="output").inc(usage.output)
        if usage.cached:
            LLM_TOKENS.labels(model=self._model, direction="cached").inc(usage.cached)

    async def after_tool_call(self, ctx, agent, call, result):  # noqa: ANN001, ANN201
        if _PROM_AVAILABLE:
            TOOL_CALLS.labels(
                tool=call.name, outcome="success" if result.success else "error"
            ).inc()
        return None

    async def on_run_end(self, ctx, agent, outcome) -> None:  # noqa: ANN001
        if not _PROM_AVAILABLE:
            return
        status = getattr(outcome, "finish_reason", None) or "failed"
        if outcome.type == "run_failed":
            status = "failed"
        AGENT_RUNS.labels(agent=agent.name, outcome=status).inc()
        AGENT_RUN_DURATION.labels(agent=agent.name).observe(outcome.duration_ms / 1000)
        AGENT_TURNS.labels(agent=agent.name).observe(outcome.turns)
