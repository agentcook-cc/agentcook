"""Adapter: bridge OpenTelemetry SDK to ``agentcook_core.tracing.Tracer``.

``agentcook-core`` is stdlib-only — it cannot import ``opentelemetry``.
But core modules call ``get_tracer().start_span(...)``. This adapter
implements the core ``Tracer`` Protocol on top of the OTel SDK and is
registered at app startup via :func:`install`.

Wire flow::

    setup_telemetry(app)         # observability.py — boots OTel SDK
        └─ install()             # this module — bridges into core
            └─ agentcook_core.tracing.set_tracer(OTelTracerAdapter(...))

After install, any ``with get_tracer().start_span("...")`` call inside
multi_agent / model_router / memory / ... emits a real OTel span.

The adapter is a thin facade: ``start_span`` returns a wrapper that
proxies ``set_attribute`` and ``record_exception`` to the underlying
``opentelemetry.trace.Span``. Context propagation (parent/child) is
handled entirely by the OTel SDK's contextvar-based current-span
machinery — we just open and close.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from opentelemetry.trace import Span as OTelSpan
    from opentelemetry.trace import Tracer as OTelTracer

from agentcook_core.tracing import (
    NoOpTracer,
    Span,
    set_tracer,
)

logger = logging.getLogger(__name__)


class _OTelSpanAdapter:
    """Wraps an OTel ``Span`` + its activation token as a core ``Span``."""

    __slots__ = ("_span", "_cm")

    def __init__(self, span: OTelSpan, cm: Any) -> None:
        # ``cm`` is the OTel ``use_span`` context-manager object; we delegate
        # __enter__/__exit__ to it so the OTel current-span context is
        # correctly propagated (parent/child relationships).
        self._span = span
        self._cm = cm

    def __enter__(self) -> _OTelSpanAdapter:
        self._cm.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc is not None:
                self._span.record_exception(exc)
        finally:
            self._cm.__exit__(exc_type, exc, tb)
            self._span.end()

    def set_attribute(self, key: str, value: Any) -> None:
        try:
            self._span.set_attribute(key, value)
        except Exception:  # noqa: BLE001 — never crash core on telemetry
            pass

    def record_exception(self, exc: BaseException) -> None:
        try:
            self._span.record_exception(exc)
        except Exception:  # noqa: BLE001
            pass


class OTelTracerAdapter:
    """Implements :class:`agentcook_core.tracing.Tracer` over an OTel ``Tracer``."""

    __slots__ = ("_tracer",)

    def __init__(self, tracer: OTelTracer) -> None:
        self._tracer = tracer

    def start_span(
        self,
        name: str,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> Span:
        from opentelemetry.trace import use_span

        # Use start_span (NOT start_as_current_span) so we control activation
        # via the use_span CM inside _OTelSpanAdapter — keeps the surface
        # uniform and avoids double-activation.
        span = self._tracer.start_span(name, attributes=dict(attributes or {}))
        cm = use_span(span, end_on_exit=False)
        return _OTelSpanAdapter(span, cm)


def install(service_name: str = "agentcook") -> bool:
    """Bridge OTel into ``agentcook-core``.

    Idempotent and dependency-tolerant: if OTel is not installed (or
    not yet initialised), falls back to the core NoOp tracer and logs
    a warning. Returns True on real install, False on fallback.

    Call AFTER ``setup_telemetry(app)`` so a real :class:`TracerProvider`
    is registered.
    """
    try:
        from opentelemetry import trace as _ot_trace
    except ImportError:
        logger.info("OTel not installed — core tracing stays in NoOp mode")
        set_tracer(NoOpTracer())
        return False

    tracer = _ot_trace.get_tracer(service_name)
    set_tracer(OTelTracerAdapter(tracer))
    logger.info("Installed OTelTracerAdapter into agentcook-core (service=%s)", service_name)
    return True


__all__ = ["OTelTracerAdapter", "install"]
