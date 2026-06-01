"""Unit tests for agentcook_core.tracing module."""

from __future__ import annotations

import pytest
from agentcook_core.tracing import (
    NoOpTracer,
    Span,
    Tracer,
    get_tracer,
    reset_tracer,
    set_tracer,
)

# ---------------------------------------------------------------------------
# Recording fake for assertions
# ---------------------------------------------------------------------------


class RecordingSpan:
    """Span impl that records attribute / exception calls for inspection."""

    def __init__(self, name: str, attributes: dict | None = None) -> None:
        self.name = name
        self.attributes: dict = dict(attributes or {})
        self.exceptions: list[BaseException] = []
        self.entered: bool = False
        self.exited: bool = False
        self.exit_args: tuple = ()

    def __enter__(self) -> RecordingSpan:
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.exited = True
        self.exit_args = (exc_type, exc, tb)

    def set_attribute(self, key: str, value) -> None:
        self.attributes[key] = value

    def record_exception(self, exc: BaseException) -> None:
        self.exceptions.append(exc)


class RecordingTracer:
    """Tracer impl that records all start_span calls + returns RecordingSpans."""

    def __init__(self) -> None:
        self.spans: list[RecordingSpan] = []

    def start_span(self, name: str, *, attributes=None) -> RecordingSpan:
        span = RecordingSpan(name, attributes)
        self.spans.append(span)
        return span


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_after():
    """Ensure each test starts and ends with the NoOp default."""
    reset_tracer()
    yield
    reset_tracer()


# ---------------------------------------------------------------------------
# Protocol Conformance
# ---------------------------------------------------------------------------


class TestProtocols:
    def test_noop_tracer_satisfies_protocol(self):
        assert isinstance(NoOpTracer(), Tracer)

    def test_recording_tracer_satisfies_protocol(self):
        assert isinstance(RecordingTracer(), Tracer)

    def test_recording_span_satisfies_protocol(self):
        assert isinstance(RecordingSpan("x"), Span)


# ---------------------------------------------------------------------------
# Default + Reset
# ---------------------------------------------------------------------------


class TestDefaultTracer:
    def test_default_is_noop(self):
        assert isinstance(get_tracer(), NoOpTracer)

    def test_set_then_get(self):
        rec = RecordingTracer()
        set_tracer(rec)
        assert get_tracer() is rec

    def test_reset_restores_noop(self):
        set_tracer(RecordingTracer())
        reset_tracer()
        assert isinstance(get_tracer(), NoOpTracer)


# ---------------------------------------------------------------------------
# NoOp Behavior
# ---------------------------------------------------------------------------


class TestNoOpTracer:
    def test_start_span_returns_usable_span(self):
        span = get_tracer().start_span("anything")
        assert span is not None

    def test_noop_span_supports_context_manager(self):
        with get_tracer().start_span("noop") as span:
            assert span is not None

    def test_noop_set_attribute_does_nothing(self):
        span = get_tracer().start_span("noop")
        # Should not raise, return value ignored.
        span.set_attribute("x", 1)
        span.set_attribute("y", "z")

    def test_noop_record_exception_does_nothing(self):
        span = get_tracer().start_span("noop")
        span.record_exception(RuntimeError("boom"))

    def test_noop_with_attributes_kwarg(self):
        span = get_tracer().start_span("noop", attributes={"foo": "bar"})
        assert span is not None

    def test_noop_returns_same_shared_instance(self):
        # Implementation detail but worth pinning: NoOp uses a shared span
        # to avoid even allocation on the hot path.
        s1 = get_tracer().start_span("a")
        s2 = get_tracer().start_span("b")
        assert s1 is s2


# ---------------------------------------------------------------------------
# Recording (Injected) Behavior
# ---------------------------------------------------------------------------


class TestInjectedTracer:
    def test_records_span_name(self):
        rec = RecordingTracer()
        set_tracer(rec)
        with get_tracer().start_span("multi_agent.run"):
            pass
        assert [s.name for s in rec.spans] == ["multi_agent.run"]

    def test_records_initial_attributes(self):
        rec = RecordingTracer()
        set_tracer(rec)
        with get_tracer().start_span("model.select", attributes={"policy": "fallback"}):
            pass
        assert rec.spans[0].attributes == {"policy": "fallback"}

    def test_set_attribute_inside_span(self):
        rec = RecordingTracer()
        set_tracer(rec)
        with get_tracer().start_span("memory.write") as span:
            span.set_attribute("agentcook.memory.layer", "diary")
        assert rec.spans[0].attributes["agentcook.memory.layer"] == "diary"

    def test_context_manager_enter_exit(self):
        rec = RecordingTracer()
        set_tracer(rec)
        with get_tracer().start_span("x"):
            pass
        s = rec.spans[0]
        assert s.entered is True
        assert s.exited is True

    def test_exception_propagates(self):
        rec = RecordingTracer()
        set_tracer(rec)
        with pytest.raises(RuntimeError):
            with get_tracer().start_span("x") as span:
                span.record_exception(RuntimeError("boom"))
                raise RuntimeError("boom")
        assert rec.spans[0].exceptions  # at least one recorded

    def test_nested_spans_both_recorded(self):
        rec = RecordingTracer()
        set_tracer(rec)
        with get_tracer().start_span("outer"):
            with get_tracer().start_span("inner"):
                pass
        names = [s.name for s in rec.spans]
        assert names == ["outer", "inner"]


# ---------------------------------------------------------------------------
# Cross-module: verify span emission from real core modules
# ---------------------------------------------------------------------------


class TestCoreModuleIntegration:
    """Sanity: hitting a real core entrypoint produces the expected spans."""

    def test_compaction_emits_span(self):
        from agentcook_core.compaction import SlidingWindowCompaction
        from agentcook_core.types import Message

        rec = RecordingTracer()
        set_tracer(rec)

        strat = SlidingWindowCompaction(window_size=2)
        msgs = [
            Message(role="user", content="a"),
            Message(role="assistant", content="b"),
            Message(role="user", content="c"),
        ]
        strat.compact(msgs)

        names = [s.name for s in rec.spans]
        assert "compaction.sliding_window" in names

    def test_pruning_emits_span(self):
        from agentcook_core.pruning import DuplicatePruning
        from agentcook_core.types import Message

        rec = RecordingTracer()
        set_tracer(rec)

        DuplicatePruning(protect_recent=0).prune(
            [
                Message(role="user", content="hi"),
                Message(role="assistant", content=""),
            ]
        )
        names = [s.name for s in rec.spans]
        assert "pruning.duplicate" in names

    def test_model_router_emits_span(self):
        from agentcook_core.model_router import (
            ModelConfig,
            ModelRegistry,
            ModelRouter,
        )

        rec = RecordingTracer()
        set_tracer(rec)

        registry = ModelRegistry()
        registry.register(ModelConfig(name="gpt-test", provider="echo"))
        router = ModelRouter(registry)
        router.select()

        names = [s.name for s in rec.spans]
        assert "model.select" in names

    def test_memory_write_emits_span(self):
        from agentcook_core.memory import InMemoryStore, MemoryLayer, MemoryManager

        rec = RecordingTracer()
        set_tracer(rec)

        mgr = MemoryManager(InMemoryStore())
        mgr.write_to_layer("agent-x", MemoryLayer.MEMORY, "k", "v")

        names = [s.name for s in rec.spans]
        assert "memory.memory.write" in names

    def test_memory_read_emits_span_with_hit_attr(self):
        from agentcook_core.memory import InMemoryStore, MemoryLayer, MemoryManager

        rec = RecordingTracer()
        set_tracer(rec)

        mgr = MemoryManager(InMemoryStore())
        mgr.read_from_layer("agent-x", MemoryLayer.MEMORY, "absent")

        read_span = next(s for s in rec.spans if s.name == "memory.memory.read")
        assert read_span.attributes.get("agentcook.memory.hit") is False
