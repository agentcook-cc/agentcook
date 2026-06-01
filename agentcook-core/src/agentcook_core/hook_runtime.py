"""Hook runtime — pre/post execution pipeline for cross-cutting concerns.

Provides a typed hook system that wraps any core logic with ordered
pre-execute and post-execute steps. Typical uses: logging, metrics,
auth checks, rate limiting, tracing span injection.

Design:
- stdlib-only (no third-party imports).
- ``Hook`` Protocol is the extension point; concrete hooks implement
  ``pre_execute`` and/or ``post_execute``.
- ``HookPipeline`` executes hooks in registration order (pre: ascending,
  post: descending — onion model).
- ``HookRegistry`` organizes hooks by event type for selective dispatch.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from agentcook_core.tracing import get_tracer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Value Types
# ---------------------------------------------------------------------------


class HookEvent(str, Enum):
    """Well-known event types hooks can subscribe to."""

    AGENT_RUN = "agent_run"
    TOOL_INVOKE = "tool_invoke"
    MODEL_CALL = "model_call"
    CONNECTOR_OPEN = "connector_open"
    PLUGIN_ACTIVATE = "plugin_activate"
    MEMORY_WRITE = "memory_write"
    CUSTOM = "custom"


@dataclass(slots=True)
class HookContext:
    """Mutable context bag passed through the hook pipeline.

    Hooks can read/write ``data`` to communicate with downstream hooks
    or the core logic. ``metadata`` carries framework-injected info
    (timestamps, trace ids, etc.) and should not be modified by hooks.
    """

    event: HookEvent
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    cancelled: bool = False
    cancel_reason: str | None = None

    def cancel(self, reason: str = "cancelled by hook") -> None:
        """Signal that the core logic should be skipped."""
        self.cancelled = True
        self.cancel_reason = reason


@dataclass(frozen=True, slots=True)
class HookResult:
    """Outcome of a full pipeline execution (pre + core + post)."""

    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    hooks_executed: int = 0


class HookError(Exception):
    """Raised when a hook fails and fail_fast is enabled."""


# ---------------------------------------------------------------------------
# Hook Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Hook(Protocol):
    """Extension point for pre/post execution logic.

    Implementations may be stateful (e.g. counter-based MetricsHook).
    Both methods receive the same ``HookContext``; mutations persist
    across the pipeline.
    """

    @property
    def name(self) -> str:
        """Human-readable hook identifier."""
        ...

    def pre_execute(self, context: HookContext) -> None:
        """Called before core logic. May mutate ``context.data`` or call
        ``context.cancel()`` to skip execution."""
        ...

    def post_execute(self, context: HookContext, result: Any) -> None:
        """Called after core logic (or after cancellation).
        ``result`` is the return value of the core callable (None if cancelled)."""
        ...


# ---------------------------------------------------------------------------
# Built-in Hooks
# ---------------------------------------------------------------------------


class LoggingHook:
    """Logs pre/post events at DEBUG level."""

    def __init__(self, *, logger_name: str = "agentcook.hooks") -> None:
        self._logger = logging.getLogger(logger_name)

    @property
    def name(self) -> str:
        return "logging_hook"

    def pre_execute(self, context: HookContext) -> None:
        self._logger.debug(
            "[%s] pre_execute | event=%s data_keys=%s",
            self.name,
            context.event.value,
            list(context.data.keys()),
        )

    def post_execute(self, context: HookContext, result: Any) -> None:
        self._logger.debug(
            "[%s] post_execute | event=%s cancelled=%s",
            self.name,
            context.event.value,
            context.cancelled,
        )


class MetricsHook:
    """Collects execution counts and durations in-memory.

    Suitable for testing / dev. In production, inject a real metrics
    backend via a custom hook that pushes to Prometheus / StatsD.
    """

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._durations: dict[str, list[float]] = {}

    @property
    def name(self) -> str:
        return "metrics_hook"

    @property
    def counts(self) -> dict[str, int]:
        """Event → invocation count."""
        return dict(self._counts)

    @property
    def durations(self) -> dict[str, list[float]]:
        """Event → list of durations in ms."""
        return {k: list(v) for k, v in self._durations.items()}

    def pre_execute(self, context: HookContext) -> None:
        context.metadata["_metrics_start_ns"] = time.perf_counter_ns()

    def post_execute(self, context: HookContext, result: Any) -> None:  # noqa: ARG002
        event_key = context.event.value
        self._counts[event_key] = self._counts.get(event_key, 0) + 1

        start_ns = context.metadata.get("_metrics_start_ns")
        if start_ns is not None:
            elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
            self._durations.setdefault(event_key, []).append(elapsed_ms)

    def reset(self) -> None:
        """Clear all collected metrics."""
        self._counts.clear()
        self._durations.clear()


# ---------------------------------------------------------------------------
# HookRegistry
# ---------------------------------------------------------------------------


class HookRegistry:
    """Organizes hooks by event type for selective dispatch.

    A hook registered for ``HookEvent.CUSTOM`` with ``event_filter="*"``
    fires on all events (global hook).
    """

    def __init__(self) -> None:
        self._hooks: dict[HookEvent, list[Hook]] = {}
        self._global_hooks: list[Hook] = []

    def register(self, event: HookEvent, hook: Hook, *, global_hook: bool = False) -> None:
        """Register a hook for a specific event type.

        Args:
            event: The event type to subscribe to.
            hook: The hook implementation.
            global_hook: If True, hook fires on ALL events regardless of type.
        """
        if global_hook:
            self._global_hooks.append(hook)
            logger.debug("Registered global hook: %s", hook.name)
        else:
            self._hooks.setdefault(event, []).append(hook)
            logger.debug("Registered hook: %s for event=%s", hook.name, event.value)

    def unregister(self, hook_name: str) -> int:
        """Remove all hooks with the given name. Returns count removed."""
        removed = 0
        for event_hooks in self._hooks.values():
            before = len(event_hooks)
            event_hooks[:] = [h for h in event_hooks if h.name != hook_name]
            removed += before - len(event_hooks)

        before = len(self._global_hooks)
        self._global_hooks[:] = [h for h in self._global_hooks if h.name != hook_name]
        removed += before - len(self._global_hooks)
        return removed

    def get_hooks(self, event: HookEvent) -> list[Hook]:
        """Return hooks for event type + global hooks (in registration order)."""
        specific = self._hooks.get(event, [])
        return self._global_hooks + specific

    @property
    def total_hooks(self) -> int:
        count = len(self._global_hooks)
        for hooks in self._hooks.values():
            count += len(hooks)
        return count

    def clear(self) -> None:
        self._hooks.clear()
        self._global_hooks.clear()


# ---------------------------------------------------------------------------
# HookPipeline
# ---------------------------------------------------------------------------


class HookPipeline:
    """Execute hooks in onion order around a core callable.

    Pre-hooks run in registration order (first registered = first called).
    Post-hooks run in reverse order (last registered = first called on exit).
    This forms a symmetric "onion" wrapping pattern.

    If any pre-hook calls ``context.cancel()``, the core callable is skipped
    and post-hooks still run (with ``context.cancelled = True``).
    """

    def __init__(self, registry: HookRegistry, *, fail_fast: bool = False) -> None:
        """
        Args:
            registry: Source of hooks per event type.
            fail_fast: If True, a hook exception aborts the pipeline.
        """
        self._registry = registry
        self._fail_fast = fail_fast

    def execute(
        self,
        event: HookEvent,
        core: Callable[[], Any],
        *,
        data: dict[str, Any] | None = None,
    ) -> HookResult:
        """Run the full pre → core → post pipeline synchronously.

        Args:
            event: Event type to dispatch hooks for.
            core: Zero-arg callable representing the wrapped logic.
            data: Initial context data (hooks may mutate this).

        Returns:
            HookResult with timing, success flag, and hook count.
        """
        context = HookContext(event=event, data=data or {})
        hooks = self._registry.get_hooks(event)
        hooks_executed = 0
        start_ns = time.perf_counter_ns()
        # Span is closed in finally below — covers all return paths.
        _span = get_tracer().start_span(
            f"hook.{event.value}",
            attributes={
                "agentcook.hook.event": event.value,
                "agentcook.hook.count": len(hooks),
                "agentcook.hook.fail_fast": self._fail_fast,
            },
        )
        _span.__enter__()
        try:
            return self._execute_inner(
                event, core, context, hooks, hooks_executed, start_ns
            )
        finally:
            _span.__exit__(None, None, None)

    def _execute_inner(
        self,
        event: HookEvent,
        core: Callable[[], Any],
        context: HookContext,
        hooks: list,
        hooks_executed: int,
        start_ns: int,
    ) -> HookResult:

        # --- Pre-execute ---
        for hook in hooks:
            try:
                hook.pre_execute(context)
                hooks_executed += 1
            except Exception as exc:
                if self._fail_fast:
                    elapsed = (time.perf_counter_ns() - start_ns) / 1_000_000
                    return HookResult(
                        success=False,
                        error=f"pre_execute failed in {hook.name}: {exc}",
                        duration_ms=elapsed,
                        hooks_executed=hooks_executed,
                    )
                logger.warning("Hook %s.pre_execute raised: %s", hook.name, exc)

            if context.cancelled:
                break

        # --- Core logic ---
        output: Any = None
        error: str | None = None
        if not context.cancelled:
            try:
                output = core()
            except Exception as exc:
                error = str(exc)
                if self._fail_fast:
                    elapsed = (time.perf_counter_ns() - start_ns) / 1_000_000
                    # Still run post hooks on error
                    for hook in reversed(hooks):
                        try:
                            hook.post_execute(context, None)
                        except Exception:
                            pass
                    return HookResult(
                        success=False,
                        output=None,
                        error=error,
                        duration_ms=elapsed,
                        hooks_executed=hooks_executed,
                    )

        # --- Post-execute (reverse order) ---
        for hook in reversed(hooks):
            try:
                hook.post_execute(context, output)
                hooks_executed += 1
            except Exception as exc:
                if self._fail_fast:
                    elapsed = (time.perf_counter_ns() - start_ns) / 1_000_000
                    return HookResult(
                        success=False,
                        error=f"post_execute failed in {hook.name}: {exc}",
                        duration_ms=elapsed,
                        hooks_executed=hooks_executed,
                    )
                logger.warning("Hook %s.post_execute raised: %s", hook.name, exc)

        elapsed = (time.perf_counter_ns() - start_ns) / 1_000_000
        success = error is None and not context.cancelled

        return HookResult(
            success=success,
            output=output,
            error=error or context.cancel_reason,
            duration_ms=elapsed,
            hooks_executed=hooks_executed,
        )


__all__ = [
    "Hook",
    "HookContext",
    "HookError",
    "HookEvent",
    "HookPipeline",
    "HookRegistry",
    "HookResult",
    "LoggingHook",
    "MetricsHook",
]
