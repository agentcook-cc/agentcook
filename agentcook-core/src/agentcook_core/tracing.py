"""Distributed-tracing surface for agentcook-core (stdlib-only).

``agentcook-core`` has a hard rule: no third-party imports. But we want
core modules (multi_agent / model_router / memory / ...) to produce
OpenTelemetry spans when the application is wired up with the OTel SDK.

The reconciliation: this module defines a minimal ``Tracer`` Protocol
that core modules call. The default global tracer is a ``NoOpTracer``
that does literally nothing. At application startup, ``agentcook`` (the
runtime package, which *does* ship OTel deps) registers an adapter via
:func:`set_tracer` that bridges the Protocol calls to the real OTel
``Tracer``.

Wire flow::

    agentcook_core.multi_agent.MultiAgentOrchestrator.run
        └─ with get_tracer().start_span("multi_agent.run", attrs={...}):
                                        │
                                        ▼
                            module-global `_tracer` (default NoOp,
                            replaced at startup by OTel adapter)

This module is intentionally tiny and side-effect free. Tests can swap
in a recording tracer to assert span structure without booting OTel.

Conventions for span names (kept short, dot-namespaced):
    multi_agent.run / multi_agent.node
    mcp.tool.invoke / mcp.client.connect
    connector.{kind}.open
    model.select
    hook.{event}
    memory.{layer}.{op}            # e.g. memory.diary.write
    memory.semantic_search
    compaction.{strategy}
    pruning.{strategy}
"""

from __future__ import annotations

from collections.abc import Mapping
from types import TracebackType
from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class Span(Protocol):
    """Minimal span surface used by core modules.

    Used as a context manager — ``__exit__`` ends the span. Concrete
    adapters may also surface ``record_exception`` and ``set_status``;
    those are not required for core, which leaves error semantics to the
    OTel auto-instrumentation around the FastAPI / DB layers.
    """

    def __enter__(self) -> Span: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    def set_attribute(self, key: str, value: Any) -> None:
        """Attach a single attribute to the span."""
        ...

    def record_exception(self, exc: BaseException) -> None:
        """Note that *exc* was raised inside this span."""
        ...


@runtime_checkable
class Tracer(Protocol):
    """Factory for spans. Implementations are expected to be cheap."""

    def start_span(
        self,
        name: str,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> Span:
        """Open a span named *name* with optional initial attributes."""
        ...


# ---------------------------------------------------------------------------
# No-op default
# ---------------------------------------------------------------------------


class _NoOpSpan:
    """Span implementation that costs almost nothing.

    All methods are present so call sites don't crash when the OTel SDK
    isn't installed (the common case in unit tests).
    """

    __slots__ = ()

    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: ARG002
        return None

    def record_exception(self, exc: BaseException) -> None:  # noqa: ARG002
        return None


class NoOpTracer:
    """Default global tracer. Returns the same shared :class:`_NoOpSpan`."""

    __slots__ = ()

    _SHARED_SPAN = _NoOpSpan()

    def start_span(
        self,
        name: str,  # noqa: ARG002
        *,
        attributes: Mapping[str, Any] | None = None,  # noqa: ARG002
    ) -> Span:
        return self._SHARED_SPAN


# ---------------------------------------------------------------------------
# Global registration
# ---------------------------------------------------------------------------


_tracer: Tracer = NoOpTracer()


def set_tracer(tracer: Tracer) -> None:
    """Install *tracer* as the process-wide tracer.

    Called once at application startup by the runtime package. Subsequent
    calls overwrite — useful for tests that need to swap in a recording
    tracer.
    """
    global _tracer
    _tracer = tracer


def get_tracer() -> Tracer:
    """Return the currently installed tracer."""
    return _tracer


def reset_tracer() -> None:
    """Restore the default :class:`NoOpTracer`. Test helper."""
    global _tracer
    _tracer = NoOpTracer()


__all__ = [
    "NoOpTracer",
    "Span",
    "Tracer",
    "get_tracer",
    "reset_tracer",
    "set_tracer",
]
