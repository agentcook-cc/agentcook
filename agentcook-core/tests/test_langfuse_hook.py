"""Unit tests for agentcook_core.langfuse_hook module."""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from agentcook_core.langfuse_hook import (
    LangfuseHook,
    NoOpHook,
    get_langfuse_hook,
    reset_langfuse_hook,
    set_langfuse_hook,
)


# ---------------------------------------------------------------------------
# Recording fake — same pattern as test_tracing.py's RecordingTracer
# ---------------------------------------------------------------------------


class RecordingHook:
    """Hook impl that records each observe_model_call invocation."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.flush_count: int = 0

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
        self.calls.append(
            {
                "model": model,
                "provider": provider,
                "prompt": prompt,
                "completion": completion,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms": latency_ms,
                "cost_usd": cost_usd,
                "metadata": dict(metadata or {}),
            }
        )

    def flush(self) -> None:
        self.flush_count += 1


class RaisingHook:
    """Hook that always raises — verifies caller-side exception isolation."""

    def observe_model_call(self, **_kw: Any) -> None:
        raise RuntimeError("simulated telemetry outage")

    def flush(self) -> None:
        raise RuntimeError("simulated flush failure")


@pytest.fixture(autouse=True)
def _reset_after():
    """Ensure each test starts and ends with the NoOp default."""
    reset_langfuse_hook()
    yield
    reset_langfuse_hook()


# ---------------------------------------------------------------------------
# Protocol Conformance
# ---------------------------------------------------------------------------


class TestProtocols:
    def test_noop_hook_satisfies_protocol(self):
        assert isinstance(NoOpHook(), LangfuseHook)

    def test_recording_hook_satisfies_protocol(self):
        assert isinstance(RecordingHook(), LangfuseHook)


# ---------------------------------------------------------------------------
# Default + Reset
# ---------------------------------------------------------------------------


class TestDefaultHook:
    def test_default_is_noop(self):
        assert isinstance(get_langfuse_hook(), NoOpHook)

    def test_set_then_get(self):
        rec = RecordingHook()
        set_langfuse_hook(rec)
        assert get_langfuse_hook() is rec

    def test_reset_restores_noop(self):
        set_langfuse_hook(RecordingHook())
        reset_langfuse_hook()
        assert isinstance(get_langfuse_hook(), NoOpHook)


# ---------------------------------------------------------------------------
# NoOp behavior
# ---------------------------------------------------------------------------


class TestNoOpHook:
    def test_observe_does_nothing(self):
        # Should not raise, returns None.
        get_langfuse_hook().observe_model_call(
            model="gpt-4o-mini",
            provider="openai",
            prompt="hi",
            completion="hello",
            prompt_tokens=12,
            completion_tokens=3,
            latency_ms=42.5,
            cost_usd=0.0002,
            metadata={"event": "test"},
        )

    def test_flush_does_nothing(self):
        get_langfuse_hook().flush()


# ---------------------------------------------------------------------------
# Recording behavior
# ---------------------------------------------------------------------------


class TestInjectedHook:
    def test_records_full_call_shape(self):
        rec = RecordingHook()
        set_langfuse_hook(rec)
        rec_hook = get_langfuse_hook()
        rec_hook.observe_model_call(
            model="gpt-4o",
            provider="openai",
            prompt="hi",
            completion="hello",
            prompt_tokens=10,
            completion_tokens=2,
            latency_ms=33.3,
            cost_usd=0.0001,
            metadata={"event": "model.chat"},
        )
        assert len(rec.calls) == 1
        call = rec.calls[0]
        assert call["model"] == "gpt-4o"
        assert call["provider"] == "openai"
        assert call["prompt_tokens"] == 10
        assert call["completion_tokens"] == 2
        assert call["latency_ms"] == 33.3
        assert call["metadata"] == {"event": "model.chat"}

    def test_records_minimal_call(self):
        rec = RecordingHook()
        set_langfuse_hook(rec)
        get_langfuse_hook().observe_model_call(model="m", provider="p")
        assert len(rec.calls) == 1
        call = rec.calls[0]
        assert call["prompt_tokens"] == 0
        assert call["completion_tokens"] == 0
        assert call["latency_ms"] == 0.0

    def test_flush_counts(self):
        rec = RecordingHook()
        set_langfuse_hook(rec)
        get_langfuse_hook().flush()
        get_langfuse_hook().flush()
        assert rec.flush_count == 2


# ---------------------------------------------------------------------------
# Cross-module: verify the model_router actually fires the hook
# ---------------------------------------------------------------------------


class TestModelRouterIntegration:
    """If this test ever breaks, model_router stopped reporting to Langfuse."""

    def test_select_emits_model_selected_event(self):
        from agentcook_core.model_router import (
            ModelConfig,
            ModelRegistry,
            ModelRouter,
            RoutingPolicy,
        )

        rec = RecordingHook()
        set_langfuse_hook(rec)

        registry = ModelRegistry()
        registry.register(
            ModelConfig(name="gpt-test", provider="openai", quality_score=80)
        )
        registry.register(
            ModelConfig(name="qwen-test", provider="qwen", quality_score=60)
        )
        router = ModelRouter(registry, policy=RoutingPolicy.QUALITY_FIRST)
        router.select()

        # model_router should report exactly the model it picked.
        assert len(rec.calls) == 1
        call = rec.calls[0]
        assert call["model"] == "gpt-test"
        assert call["provider"] == "openai"
        assert call["metadata"]["event"] == "model.selected"
        assert call["metadata"]["policy"] == "quality_first"

    def test_select_swallows_hook_exception(self):
        """A failing hook must never block model selection."""
        from agentcook_core.model_router import (
            ModelConfig,
            ModelRegistry,
            ModelRouter,
        )

        set_langfuse_hook(RaisingHook())

        registry = ModelRegistry()
        registry.register(ModelConfig(name="m", provider="p"))
        router = ModelRouter(registry)

        # Must not raise.
        result = router.select()
        assert result.model.name == "m"
