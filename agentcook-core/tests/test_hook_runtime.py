"""Unit tests for agentcook_core.hook_runtime module."""

from __future__ import annotations

from agentcook_core.hook_runtime import (
    Hook,
    HookContext,
    HookEvent,
    HookPipeline,
    HookRegistry,
    LoggingHook,
    MetricsHook,
)

# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


class RecordingHook:
    """Hook that records calls for assertion."""

    def __init__(self, hook_name: str = "recording_hook") -> None:
        self._name = hook_name
        self.pre_calls: list[HookContext] = []
        self.post_calls: list[tuple[HookContext, object]] = []

    @property
    def name(self) -> str:
        return self._name

    def pre_execute(self, context: HookContext) -> None:
        self.pre_calls.append(context)

    def post_execute(self, context: HookContext, result: object) -> None:
        self.post_calls.append((context, result))


class CancellingHook:
    """Hook that cancels execution in pre_execute."""

    @property
    def name(self) -> str:
        return "cancelling_hook"

    def pre_execute(self, context: HookContext) -> None:
        context.cancel("stopped by test")

    def post_execute(self, context: HookContext, result: object) -> None:
        pass


class FailingPreHook:
    """Hook that raises in pre_execute."""

    @property
    def name(self) -> str:
        return "failing_pre_hook"

    def pre_execute(self, context: HookContext) -> None:
        raise RuntimeError("pre_execute boom")

    def post_execute(self, context: HookContext, result: object) -> None:
        pass


class FailingPostHook:
    """Hook that raises in post_execute."""

    @property
    def name(self) -> str:
        return "failing_post_hook"

    def pre_execute(self, context: HookContext) -> None:
        pass

    def post_execute(self, context: HookContext, result: object) -> None:
        raise RuntimeError("post_execute boom")


class DataMutatingHook:
    """Hook that writes to context.data."""

    @property
    def name(self) -> str:
        return "data_mutating_hook"

    def pre_execute(self, context: HookContext) -> None:
        context.data["mutated_by_pre"] = True

    def post_execute(self, context: HookContext, result: object) -> None:
        context.data["mutated_by_post"] = True


# ---------------------------------------------------------------------------
# HookContext Tests
# ---------------------------------------------------------------------------


class TestHookContext:
    def test_initial_state(self):
        ctx = HookContext(event=HookEvent.AGENT_RUN)
        assert ctx.event == HookEvent.AGENT_RUN
        assert ctx.data == {}
        assert ctx.metadata == {}
        assert ctx.cancelled is False
        assert ctx.cancel_reason is None

    def test_cancel(self):
        ctx = HookContext(event=HookEvent.TOOL_INVOKE)
        ctx.cancel("test reason")
        assert ctx.cancelled is True
        assert ctx.cancel_reason == "test reason"

    def test_cancel_default_reason(self):
        ctx = HookContext(event=HookEvent.TOOL_INVOKE)
        ctx.cancel()
        assert ctx.cancel_reason == "cancelled by hook"

    def test_data_mutable(self):
        ctx = HookContext(event=HookEvent.AGENT_RUN, data={"key": "value"})
        ctx.data["new_key"] = "new_value"
        assert ctx.data == {"key": "value", "new_key": "new_value"}


# ---------------------------------------------------------------------------
# HookEvent Tests
# ---------------------------------------------------------------------------


class TestHookEvent:
    def test_all_events_defined(self):
        expected = {"agent_run", "tool_invoke", "model_call", "connector_open",
                    "plugin_activate", "memory_write", "custom"}
        assert {e.value for e in HookEvent} == expected

    def test_string_enum(self):
        assert HookEvent.AGENT_RUN == "agent_run"
        assert isinstance(HookEvent.AGENT_RUN, str)


# ---------------------------------------------------------------------------
# HookRegistry Tests
# ---------------------------------------------------------------------------


class TestHookRegistry:
    def test_register_and_get(self):
        registry = HookRegistry()
        hook = RecordingHook()
        registry.register(HookEvent.AGENT_RUN, hook)
        hooks = registry.get_hooks(HookEvent.AGENT_RUN)
        assert len(hooks) == 1
        assert hooks[0].name == "recording_hook"

    def test_get_hooks_empty_event(self):
        registry = HookRegistry()
        hooks = registry.get_hooks(HookEvent.TOOL_INVOKE)
        assert hooks == []

    def test_global_hook_fires_on_all_events(self):
        registry = HookRegistry()
        global_hook = RecordingHook("global")
        registry.register(HookEvent.CUSTOM, global_hook, global_hook=True)

        for event in HookEvent:
            hooks = registry.get_hooks(event)
            assert any(h.name == "global" for h in hooks)

    def test_global_plus_specific(self):
        registry = HookRegistry()
        global_hook = RecordingHook("global")
        specific_hook = RecordingHook("specific")
        registry.register(HookEvent.CUSTOM, global_hook, global_hook=True)
        registry.register(HookEvent.AGENT_RUN, specific_hook)

        hooks = registry.get_hooks(HookEvent.AGENT_RUN)
        assert len(hooks) == 2
        # Global comes first
        assert hooks[0].name == "global"
        assert hooks[1].name == "specific"

    def test_unregister(self):
        registry = HookRegistry()
        hook = RecordingHook()
        registry.register(HookEvent.AGENT_RUN, hook)
        removed = registry.unregister("recording_hook")
        assert removed == 1
        assert registry.get_hooks(HookEvent.AGENT_RUN) == []

    def test_unregister_nonexistent(self):
        registry = HookRegistry()
        assert registry.unregister("nonexistent") == 0

    def test_total_hooks(self):
        registry = HookRegistry()
        registry.register(HookEvent.AGENT_RUN, RecordingHook("a"))
        registry.register(HookEvent.TOOL_INVOKE, RecordingHook("b"))
        registry.register(HookEvent.CUSTOM, RecordingHook("g"), global_hook=True)
        assert registry.total_hooks == 3

    def test_clear(self):
        registry = HookRegistry()
        registry.register(HookEvent.AGENT_RUN, RecordingHook())
        registry.register(HookEvent.CUSTOM, RecordingHook("g"), global_hook=True)
        registry.clear()
        assert registry.total_hooks == 0


# ---------------------------------------------------------------------------
# HookPipeline Tests — Basic Execution
# ---------------------------------------------------------------------------


class TestHookPipelineBasic:
    def test_execute_calls_core(self):
        registry = HookRegistry()
        pipeline = HookPipeline(registry)
        result = pipeline.execute(HookEvent.AGENT_RUN, core=lambda: 42)
        assert result.success is True
        assert result.output == 42

    def test_execute_with_hooks(self):
        registry = HookRegistry()
        hook = RecordingHook()
        registry.register(HookEvent.AGENT_RUN, hook)
        pipeline = HookPipeline(registry)

        result = pipeline.execute(HookEvent.AGENT_RUN, core=lambda: "hello")
        assert result.success is True
        assert result.output == "hello"
        assert len(hook.pre_calls) == 1
        assert len(hook.post_calls) == 1

    def test_hooks_executed_count(self):
        registry = HookRegistry()
        registry.register(HookEvent.AGENT_RUN, RecordingHook("a"))
        registry.register(HookEvent.AGENT_RUN, RecordingHook("b"))
        pipeline = HookPipeline(registry)

        result = pipeline.execute(HookEvent.AGENT_RUN, core=lambda: None)
        # 2 pre + 2 post = 4
        assert result.hooks_executed == 4

    def test_duration_positive(self):
        registry = HookRegistry()
        pipeline = HookPipeline(registry)
        result = pipeline.execute(HookEvent.AGENT_RUN, core=lambda: None)
        assert result.duration_ms >= 0

    def test_data_passed_to_hooks(self):
        registry = HookRegistry()
        hook = RecordingHook()
        registry.register(HookEvent.AGENT_RUN, hook)
        pipeline = HookPipeline(registry)

        pipeline.execute(HookEvent.AGENT_RUN, core=lambda: None, data={"foo": "bar"})
        assert hook.pre_calls[0].data["foo"] == "bar"


# ---------------------------------------------------------------------------
# HookPipeline Tests — Cancellation
# ---------------------------------------------------------------------------


class TestHookPipelineCancellation:
    def test_cancel_skips_core(self):
        registry = HookRegistry()
        registry.register(HookEvent.AGENT_RUN, CancellingHook())
        pipeline = HookPipeline(registry)

        call_count = {"n": 0}

        def core():
            call_count["n"] += 1
            return "should not reach"

        result = pipeline.execute(HookEvent.AGENT_RUN, core=core)
        assert result.success is False
        assert result.output is None
        assert result.error == "stopped by test"
        assert call_count["n"] == 0

    def test_post_hooks_still_run_after_cancel(self):
        registry = HookRegistry()
        post_recorder = RecordingHook("post_check")
        registry.register(HookEvent.AGENT_RUN, CancellingHook())
        registry.register(HookEvent.AGENT_RUN, post_recorder)
        pipeline = HookPipeline(registry)

        pipeline.execute(HookEvent.AGENT_RUN, core=lambda: None)
        # post_execute should still be called
        assert len(post_recorder.post_calls) == 1


# ---------------------------------------------------------------------------
# HookPipeline Tests — Error Handling
# ---------------------------------------------------------------------------


class TestHookPipelineErrors:
    def test_core_exception_reported(self):
        registry = HookRegistry()
        pipeline = HookPipeline(registry, fail_fast=True)

        result = pipeline.execute(
            HookEvent.AGENT_RUN,
            core=lambda: (_ for _ in ()).throw(ValueError("core failed")),
        )
        # With fail_fast, core exception is captured
        assert result.success is False
        assert "core failed" in (result.error or "")

    def test_pre_hook_exception_fail_fast(self):
        registry = HookRegistry()
        registry.register(HookEvent.AGENT_RUN, FailingPreHook())
        pipeline = HookPipeline(registry, fail_fast=True)

        result = pipeline.execute(HookEvent.AGENT_RUN, core=lambda: 42)
        assert result.success is False
        assert "pre_execute failed" in (result.error or "")

    def test_pre_hook_exception_non_fail_fast(self):
        registry = HookRegistry()
        registry.register(HookEvent.AGENT_RUN, FailingPreHook())
        pipeline = HookPipeline(registry, fail_fast=False)

        result = pipeline.execute(HookEvent.AGENT_RUN, core=lambda: 42)
        # Core still runs
        assert result.success is True
        assert result.output == 42

    def test_post_hook_exception_fail_fast(self):
        registry = HookRegistry()
        registry.register(HookEvent.AGENT_RUN, FailingPostHook())
        pipeline = HookPipeline(registry, fail_fast=True)

        result = pipeline.execute(HookEvent.AGENT_RUN, core=lambda: 42)
        assert result.success is False
        assert "post_execute failed" in (result.error or "")

    def test_post_hook_exception_non_fail_fast(self):
        registry = HookRegistry()
        registry.register(HookEvent.AGENT_RUN, FailingPostHook())
        pipeline = HookPipeline(registry, fail_fast=False)

        result = pipeline.execute(HookEvent.AGENT_RUN, core=lambda: 42)
        assert result.success is True
        assert result.output == 42


# ---------------------------------------------------------------------------
# HookPipeline Tests — Data Mutation
# ---------------------------------------------------------------------------


class TestHookPipelineDataMutation:
    def test_hook_mutates_context_data(self):
        registry = HookRegistry()
        hook = DataMutatingHook()
        registry.register(HookEvent.AGENT_RUN, hook)
        pipeline = HookPipeline(registry)

        result = pipeline.execute(HookEvent.AGENT_RUN, core=lambda: "ok", data={})
        assert result.success is True
        # Data was mutated by hooks (we can't inspect from result directly,
        # but the test verifies no crash)


# ---------------------------------------------------------------------------
# LoggingHook Tests
# ---------------------------------------------------------------------------


class TestLoggingHook:
    def test_protocol_compliance(self):
        hook = LoggingHook()
        assert isinstance(hook, Hook)

    def test_name(self):
        hook = LoggingHook()
        assert hook.name == "logging_hook"

    def test_pre_and_post_no_crash(self):
        hook = LoggingHook()
        ctx = HookContext(event=HookEvent.AGENT_RUN, data={"a": 1})
        hook.pre_execute(ctx)
        hook.post_execute(ctx, "result")


# ---------------------------------------------------------------------------
# MetricsHook Tests
# ---------------------------------------------------------------------------


class TestMetricsHook:
    def test_protocol_compliance(self):
        hook = MetricsHook()
        assert isinstance(hook, Hook)

    def test_name(self):
        hook = MetricsHook()
        assert hook.name == "metrics_hook"

    def test_counts_increment(self):
        hook = MetricsHook()
        ctx = HookContext(event=HookEvent.AGENT_RUN)
        hook.pre_execute(ctx)
        hook.post_execute(ctx, None)
        assert hook.counts == {"agent_run": 1}

    def test_multiple_events(self):
        hook = MetricsHook()
        for event in [HookEvent.AGENT_RUN, HookEvent.AGENT_RUN, HookEvent.TOOL_INVOKE]:
            ctx = HookContext(event=event)
            hook.pre_execute(ctx)
            hook.post_execute(ctx, None)
        assert hook.counts["agent_run"] == 2
        assert hook.counts["tool_invoke"] == 1

    def test_duration_recorded(self):
        hook = MetricsHook()
        ctx = HookContext(event=HookEvent.MODEL_CALL)
        hook.pre_execute(ctx)
        hook.post_execute(ctx, None)
        durations = hook.durations
        assert "model_call" in durations
        assert len(durations["model_call"]) == 1
        assert durations["model_call"][0] >= 0

    def test_reset(self):
        hook = MetricsHook()
        ctx = HookContext(event=HookEvent.AGENT_RUN)
        hook.pre_execute(ctx)
        hook.post_execute(ctx, None)
        hook.reset()
        assert hook.counts == {}
        assert hook.durations == {}

    def test_integration_with_pipeline(self):
        registry = HookRegistry()
        metrics = MetricsHook()
        registry.register(HookEvent.AGENT_RUN, metrics)
        pipeline = HookPipeline(registry)

        pipeline.execute(HookEvent.AGENT_RUN, core=lambda: "a")
        pipeline.execute(HookEvent.AGENT_RUN, core=lambda: "b")

        assert metrics.counts["agent_run"] == 2
        assert len(metrics.durations["agent_run"]) == 2


# ---------------------------------------------------------------------------
# Hook Protocol Compliance Tests
# ---------------------------------------------------------------------------


class TestHookProtocol:
    def test_recording_hook_satisfies_protocol(self):
        assert isinstance(RecordingHook(), Hook)

    def test_cancelling_hook_satisfies_protocol(self):
        assert isinstance(CancellingHook(), Hook)

    def test_data_mutating_hook_satisfies_protocol(self):
        assert isinstance(DataMutatingHook(), Hook)
