"""LLM-observability hook surface for agentcook-core (stdlib-only).

agentcook-core has a hard rule: zero third-party imports. But model
calls (in ``model_router``, in providers) need to report to Langfuse so
the platform owner can see prompts / completions / token usage / cost /
latency in one dashboard.

The reconciliation — same pattern ``tracing.py`` uses for OTel:

- This module defines a minimal ``LangfuseHook`` Protocol that core
  modules call.
- The default global hook is ``NoOpHook`` — literally does nothing.
- At application startup, ``agentcook-swarm/services/agent-core``
  (which DOES ship the langfuse SDK) registers a real adapter via
  :func:`set_langfuse_hook` that bridges Protocol calls to the SDK.

So ``model_router.select()`` and downstream provider calls can fire
``get_langfuse_hook().observe_model_call(...)`` without ever importing
``langfuse``. Tests inject a recording hook to assert what would have
been reported.

The Protocol surface is narrow on purpose — Langfuse's full
``Trace/Span/Generation`` taxonomy is rich, but agentcook-core only
needs to report one thing: "a model call happened, here is the
input/output/metadata". The adapter is free to map that onto Langfuse
``Generation`` objects however it likes.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class LangfuseHook(Protocol):
    """Reports an LLM call event to Langfuse (or anywhere else).

    Implementations are expected to be cheap and exception-safe — a
    telemetry failure must never propagate into the caller. The adapter
    in the application layer is responsible for swallowing SDK errors.
    """

    def observe_model_call(
        self,
        *,
        model: str,
        provider: str,
        prompt: str | list | None = None,
        completion: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: float = 0.0,
        cost_usd: float = 0.0,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Record one model call. All fields are optional except ``model``+``provider``."""
        ...

    def flush(self) -> None:
        """Block until in-flight telemetry has been delivered. Tests may rely on this."""
        ...


# ---------------------------------------------------------------------------
# No-op default
# ---------------------------------------------------------------------------


class NoOpHook:
    """Default global hook — does nothing. Cheap enough to live on the hot path."""

    __slots__ = ()

    def observe_model_call(
        self,
        *,
        model: str,  # noqa: ARG002
        provider: str,  # noqa: ARG002
        prompt: str | list | None = None,  # noqa: ARG002
        completion: str | None = None,  # noqa: ARG002
        prompt_tokens: int = 0,  # noqa: ARG002
        completion_tokens: int = 0,  # noqa: ARG002
        latency_ms: float = 0.0,  # noqa: ARG002
        cost_usd: float = 0.0,  # noqa: ARG002
        metadata: Mapping[str, Any] | None = None,  # noqa: ARG002
    ) -> None:
        return None

    def flush(self) -> None:
        return None


# ---------------------------------------------------------------------------
# Global registration
# ---------------------------------------------------------------------------


_hook: LangfuseHook = NoOpHook()


def set_langfuse_hook(hook: LangfuseHook) -> None:
    """Install *hook* as the process-wide Langfuse hook.

    Called once at application startup by the runtime / swarm service.
    Subsequent calls overwrite — useful for tests that need to inject a
    recording hook then restore.
    """
    global _hook
    _hook = hook


def get_langfuse_hook() -> LangfuseHook:
    """Return the currently installed Langfuse hook."""
    return _hook


def reset_langfuse_hook() -> None:
    """Restore the default :class:`NoOpHook`. Test helper."""
    global _hook
    _hook = NoOpHook()


__all__ = [
    "LangfuseHook",
    "NoOpHook",
    "get_langfuse_hook",
    "reset_langfuse_hook",
    "set_langfuse_hook",
]
