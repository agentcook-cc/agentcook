"""Prometheus-backed Hook implementation — bridges agentcook-core hook_runtime to prometheus_client.

Day 32 LLM GAP backlog — replaces the in-memory MetricsHook with real
Prometheus counters and histograms for production observability.

Usage::

    from agentcook_app.hooks_prometheus import PrometheusHook
    from agentcook_core.hook_runtime import HookEvent, HookRegistry, HookPipeline

    registry = HookRegistry()
    prom_hook = PrometheusHook()
    registry.register(HookEvent.CUSTOM, prom_hook, global_hook=True)

    pipeline = HookPipeline(registry)
    pipeline.execute(HookEvent.MODEL_CALL, core=lambda: call_llm(), data={"model": "gpt-4o"})
    # → agentcook_hook_executions_total{event="model_call"} increments
    # → agentcook_hook_duration_seconds{event="model_call"} records latency
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_PROM_AVAILABLE = False

try:
    from prometheus_client import Counter, Histogram

    _PROM_AVAILABLE = True
except ImportError:
    pass

if _PROM_AVAILABLE:
    from agentcook_core.hook_runtime import HookContext

    HOOK_EXECUTIONS = Counter(
        "agentcook_hook_executions_total",
        "Total hook pipeline executions by event type and outcome",
        ["event", "outcome"],
    )

    HOOK_DURATION = Histogram(
        "agentcook_hook_duration_seconds",
        "Hook pipeline execution duration in seconds",
        ["event"],
        buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    )

    MODEL_SELECTIONS = Counter(
        "agentcook_model_selections_total",
        "Model router selections by model name and policy",
        ["model", "policy"],
    )

    MODEL_FALLBACKS = Counter(
        "agentcook_model_fallbacks_total",
        "Model router fallback attempts (model was unavailable)",
        ["model"],
    )


class PrometheusHook:
    """Hook that pushes execution metrics to Prometheus.

    Gracefully no-ops when prometheus_client is not installed.
    Designed to be registered as a global hook (fires on all events).
    """

    @property
    def name(self) -> str:
        return "prometheus_hook"

    def pre_execute(self, context: Any) -> None:
        if not _PROM_AVAILABLE:
            return
        context.metadata["_prom_start"] = time.perf_counter()

    def post_execute(self, context: Any, result: Any) -> None:
        if not _PROM_AVAILABLE:
            return

        event_name = context.event.value
        outcome = "cancelled" if context.cancelled else ("error" if context.cancelled else "success")

        # Determine actual outcome from HookResult if available
        if hasattr(result, "success"):
            outcome = "success" if result.success else "error"
        elif context.cancelled:
            outcome = "cancelled"

        HOOK_EXECUTIONS.labels(event=event_name, outcome=outcome).inc()

        start = context.metadata.get("_prom_start")
        if start is not None:
            elapsed = time.perf_counter() - start
            HOOK_DURATION.labels(event=event_name).observe(elapsed)

        # Track model selection events specifically
        if event_name == "model_call" and "model" in context.data:
            policy = context.data.get("policy", "unknown")
            MODEL_SELECTIONS.labels(
                model=context.data["model"],
                policy=policy,
            ).inc()

        # Track fallback events
        if "fallback_from" in context.data:
            MODEL_FALLBACKS.labels(model=context.data["fallback_from"]).inc()


def is_available() -> bool:
    """Check if prometheus_client is installed."""
    return _PROM_AVAILABLE
