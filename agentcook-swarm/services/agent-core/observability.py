"""OpenTelemetry auto-instrumentation for the agent-core service.

Wires HTTP (FastAPI), gRPC (server + client), and base Python logging
into the OTel SDK so spans + metrics flow out via OTLP gRPC to the
collector at ``OTEL_EXPORTER_OTLP_ENDPOINT`` (default
``http://otel-collector:4317``).

Degrades gracefully: if any OTel package is missing, ``setup_telemetry``
logs a warning and returns False — the service still runs, just without
telemetry. This lets local dev (``pip install agentcook[base]``) work
without the full observability extra.

Call sites:

- ``main.create_app()`` calls ``setup_telemetry(app)`` before
  registering any routes so the FastAPI middleware wraps every handler.
- ``grpc_server.serve_grpc`` calls ``setup_grpc_server_instrumentation()``
  before binding the server so the gRPC service spans are emitted.

Environment variables read:

- ``OTEL_SERVICE_NAME``         — service name on the span (default ``agent-core``)
- ``OTEL_EXPORTER_OTLP_ENDPOINT`` — collector gRPC endpoint
- ``DEPLOY_ENV``                — ``deployment.environment`` resource attr (default ``dev``)
- ``AGENTCOOK_VERSION``         — ``service.version`` resource attr (default ``0.1.0``)
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


# Lazy-imported instrumentors — each may be present independently of the
# core SDK above.
_FASTAPI_AVAILABLE = False
_GRPC_AVAILABLE = False
_LOGGING_AVAILABLE = False

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: F401

    _FASTAPI_AVAILABLE = True
except ImportError:
    pass

try:
    from opentelemetry.instrumentation.grpc import (  # noqa: F401
        GrpcAioInstrumentorClient,
        GrpcAioInstrumentorServer,
    )

    _GRPC_AVAILABLE = True
except ImportError:
    pass

try:
    from opentelemetry.instrumentation.logging import LoggingInstrumentor  # noqa: F401

    _LOGGING_AVAILABLE = True
except ImportError:
    pass


DEFAULT_OTLP_ENDPOINT = "http://otel-collector:4317"
DEFAULT_SERVICE_NAME = "agent-core"


def _build_resource() -> object | None:
    """Construct the Resource carrying service identity attributes."""
    if not _OTEL_AVAILABLE:
        return None
    return Resource.create(
        {
            "service.name": os.getenv("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME),
            "service.version": os.getenv("AGENTCOOK_VERSION", "0.1.0"),
            "deployment.environment": os.getenv("DEPLOY_ENV", "dev"),
        }
    )


def _install_tracer_provider() -> object | None:
    """Register a TracerProvider with OTLP gRPC export."""
    if not _OTEL_AVAILABLE:
        return None
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", DEFAULT_OTLP_ENDPOINT)
    provider = TracerProvider(resource=_build_resource())
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(provider)
    return provider


def _install_meter_provider() -> object | None:
    """Register a MeterProvider with periodic OTLP metric export."""
    if not _OTEL_AVAILABLE:
        return None
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", DEFAULT_OTLP_ENDPOINT)
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=True),
        export_interval_millis=15_000,
    )
    provider = MeterProvider(resource=_build_resource(), metric_readers=[reader])
    metrics.set_meter_provider(provider)
    return provider


def setup_telemetry(app: "FastAPI" | None = None) -> bool:
    """Wire OTel SDK + FastAPI auto-instrumentation.

    Returns True if real OTel was installed, False if the SDK is
    missing (NoOp degraded mode). Idempotent — calling twice silently
    overwrites the previous providers.
    """
    if not _OTEL_AVAILABLE:
        logger.info(
            "OpenTelemetry SDK not installed — telemetry disabled. "
            "Install with: pip install opentelemetry-sdk "
            "opentelemetry-exporter-otlp-proto-grpc "
            "opentelemetry-instrumentation-fastapi "
            "opentelemetry-instrumentation-grpc"
        )
        return False

    _install_tracer_provider()
    _install_meter_provider()

    if app is not None and _FASTAPI_AVAILABLE:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,
            # Health probes + spec endpoints are noisy and irrelevant.
            excluded_urls="health,health/ready,metrics,openapi.json,docs,redoc",
        )
        logger.info("FastAPI auto-instrumentation enabled")

    if _LOGGING_AVAILABLE:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor

        LoggingInstrumentor().instrument(set_logging_format=True)

    # Bridge OTel into agentcook-core (so model_router / memory / etc spans
    # land in the same trace tree as the HTTP request). Best-effort — if
    # the bridge isn't available, core stays in NoOp mode.
    try:
        from agentcook_app.otel_tracer_adapter import install as _install_core

        _install_core(service_name=os.getenv("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME))
        logger.info("Bridged OTel into agentcook-core")
    except Exception:  # noqa: BLE001 — telemetry must never crash the app
        logger.warning("agentcook-core tracer bridge unavailable", exc_info=True)

    # Bridge Langfuse into agentcook-core (so model_router.select and
    # OpenAIProvider.chat report LLM generations). Same isolation rules:
    # NoOp on any failure, never propagate.
    try:
        from langfuse_adapter import install as _install_langfuse

        _install_langfuse()
    except Exception:  # noqa: BLE001
        logger.warning("Langfuse adapter install failed (NoOp)", exc_info=True)

    return True


def setup_grpc_server_instrumentation() -> bool:
    """Enable OTel server-side spans for any aio gRPC server started after this call.

    Must be called BEFORE ``grpc.aio.server()`` is constructed, otherwise
    the interceptor doesn't see new servers. Returns True if the gRPC
    instrumentor is installed, False otherwise.
    """
    if not _GRPC_AVAILABLE:
        logger.info("opentelemetry-instrumentation-grpc not installed — gRPC spans disabled")
        return False
    from opentelemetry.instrumentation.grpc import GrpcAioInstrumentorServer

    GrpcAioInstrumentorServer().instrument()
    logger.info("gRPC server auto-instrumentation enabled")
    return True


def setup_grpc_client_instrumentation() -> bool:
    """Enable OTel client-side spans for outbound aio gRPC channels.

    Connector uses this when it constructs the channel to agent-core,
    so the trace context propagates across the service boundary.
    """
    if not _GRPC_AVAILABLE:
        return False
    from opentelemetry.instrumentation.grpc import GrpcAioInstrumentorClient

    GrpcAioInstrumentorClient().instrument()
    logger.info("gRPC client auto-instrumentation enabled")
    return True


def get_meter(name: str = DEFAULT_SERVICE_NAME) -> object | None:
    """Return an OTel Meter for hand-rolled custom metrics. None if SDK absent."""
    if not _OTEL_AVAILABLE:
        return None
    return metrics.get_meter(name)


__all__ = [
    "DEFAULT_OTLP_ENDPOINT",
    "DEFAULT_SERVICE_NAME",
    "get_meter",
    "setup_grpc_client_instrumentation",
    "setup_grpc_server_instrumentation",
    "setup_telemetry",
]
