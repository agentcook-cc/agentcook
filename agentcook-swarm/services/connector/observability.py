"""OpenTelemetry auto-instrumentation for the connector service.

Mirrors the agent-core ``observability`` module but enables the gRPC
*client* instrumentor (not server) — connector is the gRPC consumer of
agent-core's ChatService. Trace context propagates HTTP request →
FastAPI server span → gRPC client span → agent-core's gRPC server span,
all under one trace id in Jaeger.

Degrades gracefully when OTel packages are missing.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

_OTEL_AVAILABLE = False

try:
    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except ImportError:
    pass


_FASTAPI_AVAILABLE = False
_GRPC_AVAILABLE = False

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: F401

    _FASTAPI_AVAILABLE = True
except ImportError:
    pass

try:
    from opentelemetry.instrumentation.grpc import GrpcAioInstrumentorClient  # noqa: F401

    _GRPC_AVAILABLE = True
except ImportError:
    pass


DEFAULT_OTLP_ENDPOINT = "http://otel-collector:4317"
DEFAULT_SERVICE_NAME = "connector"


def _build_resource() -> object | None:
    if not _OTEL_AVAILABLE:
        return None
    return Resource.create(
        {
            "service.name": os.getenv("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME),
            "service.version": os.getenv("AGENTCOOK_VERSION", "0.1.0"),
            "deployment.environment": os.getenv("DEPLOY_ENV", "dev"),
        }
    )


def setup_telemetry(app: "FastAPI" | None = None) -> bool:
    """Wire OTel SDK + FastAPI + gRPC client auto-instrumentation."""
    if not _OTEL_AVAILABLE:
        logger.info("OpenTelemetry SDK not installed — telemetry disabled")
        return False

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", DEFAULT_OTLP_ENDPOINT)

    # Traces
    tracer_provider = TracerProvider(resource=_build_resource())
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=True),
        export_interval_millis=15_000,
    )
    metrics.set_meter_provider(
        MeterProvider(resource=_build_resource(), metric_readers=[reader])
    )

    if app is not None and _FASTAPI_AVAILABLE:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="health,metrics",
        )
        logger.info("FastAPI auto-instrumentation enabled")

    # gRPC client: instruments any aio channel created after this point,
    # which covers connector's outbound calls to agent-core.
    if _GRPC_AVAILABLE:
        from opentelemetry.instrumentation.grpc import GrpcAioInstrumentorClient

        GrpcAioInstrumentorClient().instrument()
        logger.info("gRPC client auto-instrumentation enabled")

    return True


def get_meter(name: str = DEFAULT_SERVICE_NAME) -> object | None:
    """Return an OTel Meter for custom metrics. None if SDK absent."""
    if not _OTEL_AVAILABLE:
        return None
    return metrics.get_meter(name)


__all__ = ["DEFAULT_OTLP_ENDPOINT", "DEFAULT_SERVICE_NAME", "get_meter", "setup_telemetry"]
