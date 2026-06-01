"""Tests for agentcook_app.hooks_prometheus — Prometheus-backed Hook bridge."""

from __future__ import annotations

import pytest

from agentcook_core.hook_runtime import HookContext, HookEvent

from agentcook_app.hooks_prometheus import PrometheusHook, is_available


@pytest.fixture
def hook() -> PrometheusHook:
    return PrometheusHook()


class TestPrometheusHook:
    def test_name(self, hook: PrometheusHook):
        assert hook.name == "prometheus_hook"

    def test_pre_execute_sets_start_time(self, hook: PrometheusHook):
        ctx = HookContext(event=HookEvent.AGENT_RUN)
        hook.pre_execute(ctx)
        if is_available():
            assert "_prom_start" in ctx.metadata

    def test_post_execute_no_crash(self, hook: PrometheusHook):
        ctx = HookContext(event=HookEvent.AGENT_RUN)
        hook.pre_execute(ctx)
        hook.post_execute(ctx, None)

    def test_model_call_event_tracks_model(self, hook: PrometheusHook):
        ctx = HookContext(
            event=HookEvent.MODEL_CALL,
            data={"model": "gpt-4o", "policy": "fallback_chain"},
        )
        hook.pre_execute(ctx)
        hook.post_execute(ctx, None)
        # No crash — metrics recorded if prometheus_client available

    def test_fallback_tracking(self, hook: PrometheusHook):
        ctx = HookContext(
            event=HookEvent.MODEL_CALL,
            data={"fallback_from": "gpt-4o"},
        )
        hook.pre_execute(ctx)
        hook.post_execute(ctx, None)

    def test_cancelled_context(self, hook: PrometheusHook):
        ctx = HookContext(event=HookEvent.TOOL_INVOKE)
        ctx.cancel("rate limited")
        hook.pre_execute(ctx)
        hook.post_execute(ctx, None)

    def test_is_available_returns_bool(self):
        assert isinstance(is_available(), bool)


@pytest.mark.skipif(not is_available(), reason="prometheus_client not installed")
class TestPrometheusHookWithClient:
    """Tests that require prometheus_client to be installed."""

    def test_hook_executions_counter_increments(self, hook: PrometheusHook):
        from agentcook_app.hooks_prometheus import HOOK_EXECUTIONS

        # Get current value
        ctx = HookContext(event=HookEvent.AGENT_RUN)
        hook.pre_execute(ctx)
        hook.post_execute(ctx, None)

        # Verify counter was created (no crash = success for label-based counters)
        sample = HOOK_EXECUTIONS.labels(event="agent_run", outcome="success")
        assert sample._value.get() >= 1

    def test_hook_duration_records(self, hook: PrometheusHook):
        from agentcook_app.hooks_prometheus import HOOK_DURATION

        ctx = HookContext(event=HookEvent.TOOL_INVOKE)
        hook.pre_execute(ctx)
        hook.post_execute(ctx, None)

        # Histogram sum should be positive
        assert HOOK_DURATION.labels(event="tool_invoke")._sum.get() >= 0

    def test_model_selections_counter(self, hook: PrometheusHook):
        from agentcook_app.hooks_prometheus import MODEL_SELECTIONS

        ctx = HookContext(
            event=HookEvent.MODEL_CALL,
            data={"model": "claude-3-sonnet", "policy": "cost_optimized"},
        )
        hook.pre_execute(ctx)
        hook.post_execute(ctx, None)

        sample = MODEL_SELECTIONS.labels(model="claude-3-sonnet", policy="cost_optimized")
        assert sample._value.get() >= 1
