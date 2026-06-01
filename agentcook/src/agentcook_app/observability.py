"""OpenTelemetry instrumentation for the agentcook FastAPI runtime.

Phase 2 Day 16 — Agent C.

Architecture (Day 16):
    Python SDK  ──OTLP gRPC──▸  Jaeger all-in-one (localhost:4317)

Phase 3+ will insert an OTel Collector between SDK and backends
(see ``scripts/otel-config.yaml``).

Usage in ``main.py``::

    from agentcook_app.observability import setup_telemetry
    # inside create_app():
    setup_telemetry(app)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

_OTEL_AVAILABLE = False

try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except ImportError:
    pass


SERVICE_NAME = "agentcook-python"
DEFAULT_OTLP_ENDPOINT = "http://localhost:4317"


def setup_telemetry(app: FastAPI) -> None:
    """Wire OpenTelemetry tracing into a FastAPI application.

    Gracefully no-ops when OTel packages are not installed, so the app
    can still run without the observability stack (e.g. in unit tests).
    """
    if not _OTEL_AVAILABLE:
        import logging

        logging.getLogger(__name__).info(
            "OpenTelemetry packages not installed — tracing disabled. "
            "Install with: uv add opentelemetry-sdk opentelemetry-exporter-otlp-proto-grpc "
            "opentelemetry-instrumentation-fastapi"
        )
        return

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", DEFAULT_OTLP_ENDPOINT)

    resource = Resource.create(
        {
            "service.name": SERVICE_NAME,
            "service.version": os.environ.get("AGENTCOOK_VERSION", "dev"),
            "deployment.environment": os.environ.get("AGENTCOOK_ENV", "local"),
        }
    )

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(
        app,
        # /healthz was renamed to /health + /health/ready in Day 20 (C);
        # the regex still excludes both. openapi.json and docs are noisy.
        excluded_urls="health,openapi.json,docs",
        tracer_provider=provider,
    )

    # Bridge OTel into agentcook-core so multi_agent / model_router /
    # memory / compaction / pruning / connector / hook spans show up in
    # the same trace tree as the FastAPI request span.
    try:
        from agentcook_app.otel_tracer_adapter import install as _install_core_tracer

        _install_core_tracer(service_name=SERVICE_NAME)
    except Exception:  # noqa: BLE001 — telemetry must never break the app
        import logging as _logging

        _logging.getLogger(__name__).warning(
            "Failed to install OTel adapter into agentcook-core", exc_info=True
        )


def get_tracer(name: str = __name__) -> trace.Tracer:
    """Return a tracer for manual span creation.

    Falls back to a no-op tracer when OTel is not available.
    """
    if not _OTEL_AVAILABLE:
        from opentelemetry import trace as _trace

        return _trace.get_tracer(name)
    return trace.get_tracer(name)


def enrich_current_span(**attributes: str | int | float | bool) -> None:
    """Add custom attributes to the current active span.

    Gracefully no-ops when OTel is not available or no span is active.
    Use in route handlers to attach business context::

        enrich_current_span(user_id=ctx.user_id, agent_id=agent_id)
    """
    if not _OTEL_AVAILABLE:
        return
    span = trace.get_current_span()
    if span and span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(f"agentcook.{key}", value)
