"""Unit tests for agentcook_core.pruning module."""

from __future__ import annotations

import pytest
from agentcook_core.pruning import (
    CompositePruning,
    DuplicatePruning,
    PruningResult,
    PruningStrategy,
    RelevancePruning,
)
from agentcook_core.types import Message, ToolCall

# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


class FakeEmbedder:
    """Char-frequency embedder; cosine similarity. Same shape as test_memory's."""

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * 26
        for ch in text.lower():
            if "a" <= ch <= "z":
                vec[ord(ch) - ord("a")] += 1.0
        total = sum(vec) or 1.0
        return [v / total for v in vec]

    def similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(y * y for y in b) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)


class ConstantSimilarityEmbedder:
    """Returns a fixed similarity regardless of inputs — for predictable tests."""

    def __init__(self, score: float) -> None:
        self.score = score

    def embed(self, text: str) -> list[float]:
        return [1.0]

    def similarity(self, a: list[float], b: list[float]) -> float:
        return self.score


def _msg(role: str, content: str = "x", **kw) -> Message:
    return Message(role=role, content=content, **kw)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Protocol Conformance
# ---------------------------------------------------------------------------


class TestProtocols:
    def test_relevance_satisfies_protocol(self):
        strat = RelevancePruning(FakeEmbedder())
        assert isinstance(strat, PruningStrategy)

    def test_duplicate_satisfies_protocol(self):
        strat = DuplicatePruning()
        assert isinstance(strat, PruningStrategy)

    def test_composite_satisfies_protocol(self):
        strat = CompositePruning([DuplicatePruning()])
        assert isinstance(strat, PruningStrategy)


# ---------------------------------------------------------------------------
# RelevancePruning
# ---------------------------------------------------------------------------


class TestRelevancePruning:
    def test_empty_messages(self):
        strat = RelevancePruning(FakeEmbedder())
        result = strat.prune([])
        assert result.messages == []
        assert result.dropped_count == 0

    def test_no_anchor_passthrough(self):
        # All messages are assistant-only; no user anchor exists.
        strat = RelevancePruning(FakeEmbedder())
        msgs = [_msg("assistant", "hello"), _msg("assistant", "world")]
        result = strat.prune(msgs)
        assert result.messages == msgs
        assert result.dropped_count == 0

    def test_drops_below_min_score(self):
        strat = RelevancePruning(
            ConstantSimilarityEmbedder(0.05),
            min_score=0.5,
            protect_recent=0,
            decay_half_life_turns=10_000,
        )
        msgs = [
            _msg("user", "anchor question"),
            _msg("assistant", "irrelevant noise"),
            _msg("assistant", "more noise"),
        ]
        result = strat.prune(msgs)
        # User msg is the *anchor* — but it's still scored. With score 0.05 < 0.5,
        # the user msg also gets dropped (anchor protection isn't a feature here).
        # Verify at least the assistant noise is gone.
        assert result.dropped_count >= 2
        assert all(m.role != "assistant" or m.content == "" for m in result.messages)

    def test_keeps_above_min_score(self):
        strat = RelevancePruning(
            ConstantSimilarityEmbedder(0.9),
            min_score=0.5,
            protect_recent=0,
            decay_half_life_turns=10_000,
        )
        msgs = [
            _msg("user", "anchor"),
            _msg("assistant", "relevant 1"),
            _msg("assistant", "relevant 2"),
        ]
        result = strat.prune(msgs)
        assert result.messages == msgs
        assert result.dropped_count == 0

    def test_protect_recent_never_dropped(self):
        strat = RelevancePruning(
            ConstantSimilarityEmbedder(0.0),
            min_score=0.5,
            protect_recent=2,
        )
        msgs = [
            _msg("user", "anchor"),
            _msg("assistant", "old, would be dropped"),
            _msg("assistant", "recent 1, protected"),
            _msg("assistant", "recent 2, protected"),
        ]
        result = strat.prune(msgs)
        # Last 2 always kept.
        assert msgs[-1] in result.messages
        assert msgs[-2] in result.messages

    def test_system_messages_always_kept(self):
        strat = RelevancePruning(
            ConstantSimilarityEmbedder(0.0),
            min_score=0.5,
            protect_recent=0,
        )
        sys_msg = _msg("system", "I am alice")
        msgs = [sys_msg, _msg("user", "anchor"), _msg("assistant", "noise")]
        result = strat.prune(msgs)
        assert sys_msg in result.messages

    def test_anchor_text_override(self):
        strat = RelevancePruning(
            FakeEmbedder(),
            min_score=0.0,  # keep everything; just verify anchor selection
            protect_recent=0,
            anchor_text="explicit anchor",
        )
        msgs = [_msg("user", "different content"), _msg("assistant", "x")]
        result = strat.prune(msgs)
        # No drops with min_score=0; anchor override path exercised.
        assert len(result.messages) == 2

    def test_time_decay_drops_old_messages(self):
        # similarity = 0.9 always. half_life=1 → age 10 turns → decay = 0.5^10 ≈ 0.001.
        # min_score = 0.5 → old messages drop, recent stay.
        strat = RelevancePruning(
            ConstantSimilarityEmbedder(0.9),
            min_score=0.5,
            protect_recent=0,
            decay_half_life_turns=1,
        )
        msgs = [_msg("user", "anchor")] + [_msg("assistant", f"t{i}") for i in range(10)]
        result = strat.prune(msgs)
        # Some older turns should drop due to decay.
        assert result.dropped_count > 0

    def test_empty_assistant_no_tool_calls_dropped(self):
        # Empty assistant content with no tool_calls → dropped regardless of score.
        strat = RelevancePruning(
            ConstantSimilarityEmbedder(1.0),
            min_score=0.0,
            protect_recent=0,
        )
        msgs = [
            _msg("user", "anchor"),
            _msg("assistant", ""),  # empty, no tool calls → dropped
        ]
        result = strat.prune(msgs)
        assert result.dropped_count == 1
        assert _msg("assistant", "") not in result.messages

    def test_empty_assistant_with_tool_calls_kept(self):
        strat = RelevancePruning(
            ConstantSimilarityEmbedder(1.0),
            min_score=0.0,
            protect_recent=0,
        )
        tool_msg = _msg(
            "assistant",
            "",
            tool_calls=(ToolCall(id="1", name="search", arguments={}),),
        )
        msgs = [_msg("user", "anchor"), tool_msg]
        result = strat.prune(msgs)
        assert tool_msg in result.messages

    def test_invalid_min_score_raises(self):
        with pytest.raises(ValueError):
            RelevancePruning(FakeEmbedder(), min_score=-0.1)
        with pytest.raises(ValueError):
            RelevancePruning(FakeEmbedder(), min_score=1.5)

    def test_invalid_protect_recent_raises(self):
        with pytest.raises(ValueError):
            RelevancePruning(FakeEmbedder(), protect_recent=-1)

    def test_invalid_half_life_raises(self):
        with pytest.raises(ValueError):
            RelevancePruning(FakeEmbedder(), decay_half_life_turns=0)


# ---------------------------------------------------------------------------
# DuplicatePruning
# ---------------------------------------------------------------------------


class TestDuplicatePruning:
    def test_empty_messages(self):
        result = DuplicatePruning().prune([])
        assert result.messages == []

    def test_single_message_passthrough(self):
        msgs = [_msg("user", "hi")]
        assert DuplicatePruning().prune(msgs).messages == msgs

    def test_drops_empty_assistant_no_tools(self):
        msgs = [
            _msg("user", "q"),
            _msg("assistant", ""),  # noise
            _msg("assistant", "real reply"),
        ]
        result = DuplicatePruning(protect_recent=0).prune(msgs)
        assert result.dropped_count == 1
        assert _msg("assistant", "") not in result.messages

    def test_drops_repeat_tool_call(self):
        tc1 = ToolCall(id="a", name="search", arguments={"q": "py"})
        tc2 = ToolCall(id="b", name="search", arguments={"q": "py"})  # same name+args
        msgs = [
            _msg("user", "q"),
            _msg("assistant", "", tool_calls=(tc1,)),
            _msg("assistant", "", tool_calls=(tc2,)),  # duplicate
            _msg("tool", "result", tool_call_id="b", name="search"),
        ]
        result = DuplicatePruning(protect_recent=0).prune(msgs)
        assert result.dropped_count == 1

    def test_distinct_tool_calls_kept(self):
        tc1 = ToolCall(id="a", name="search", arguments={"q": "py"})
        tc2 = ToolCall(id="b", name="search", arguments={"q": "rust"})
        msgs = [
            _msg("user", "q"),
            _msg("assistant", "", tool_calls=(tc1,)),
            _msg("assistant", "", tool_calls=(tc2,)),
        ]
        result = DuplicatePruning(protect_recent=0).prune(msgs)
        assert result.dropped_count == 0

    def test_repeat_tool_call_with_text_content_kept(self):
        # If the duplicate carries an explanation, treat as legit retry, not noise.
        tc = ToolCall(id="a", name="search", arguments={"q": "py"})
        msgs = [
            _msg("user", "q"),
            _msg("assistant", "", tool_calls=(tc,)),
            _msg("assistant", "let me retry with same args", tool_calls=(tc,)),
        ]
        result = DuplicatePruning(protect_recent=0).prune(msgs)
        # The second assistant turn has content; it should NOT be dropped.
        assert result.dropped_count == 0

    def test_drops_duplicate_user_messages(self):
        msgs = [
            _msg("user", "double clicked submit"),
            _msg("user", "double clicked submit"),
            _msg("assistant", "ok"),
        ]
        result = DuplicatePruning(protect_recent=0).prune(msgs)
        assert result.dropped_count == 1

    def test_distinct_user_messages_kept(self):
        msgs = [
            _msg("user", "first question"),
            _msg("user", "follow-up question"),
        ]
        result = DuplicatePruning(protect_recent=0).prune(msgs)
        assert result.dropped_count == 0

    def test_system_messages_always_kept(self):
        sys_a = _msg("system", "I am alice")
        sys_b = _msg("system", "I am alice")  # could be dup but never dropped
        msgs = [sys_a, sys_b, _msg("user", "hi")]
        result = DuplicatePruning(protect_recent=0).prune(msgs)
        assert sys_a in result.messages
        assert sys_b in result.messages

    def test_protect_recent_keeps_tail(self):
        msgs = [
            _msg("user", "q1"),
            _msg("assistant", ""),  # would be dropped if not protected
            _msg("assistant", ""),
        ]
        # protect_recent=2 means the last 2 (both empty) are protected.
        result = DuplicatePruning(protect_recent=2).prune(msgs)
        assert len(result.messages) == 3

    def test_invalid_protect_recent_raises(self):
        with pytest.raises(ValueError):
            DuplicatePruning(protect_recent=-1)


# ---------------------------------------------------------------------------
# CompositePruning
# ---------------------------------------------------------------------------


class TestCompositePruning:
    def test_runs_strategies_in_order(self):
        # Stage 1: dedup → drops 1 empty assistant turn.
        # Stage 2: relevance with min_score=1.1 (impossible) → drops everything except sys/protected.
        sys_msg = _msg("system", "I am alice")
        msgs = [
            sys_msg,
            _msg("user", "anchor"),
            _msg("assistant", ""),  # dropped by dedup
            _msg("assistant", "noise"),
        ]
        composite = CompositePruning([
            DuplicatePruning(protect_recent=0),
            RelevancePruning(
                ConstantSimilarityEmbedder(0.0),
                min_score=0.5,
                protect_recent=1,
            ),
        ])
        result = composite.prune(msgs)
        # System message survives both stages.
        assert sys_msg in result.messages
        # Per-stage drop counts recorded.
        assert "per_stage_dropped" in result.metadata
        assert result.dropped_count == sum(result.metadata["per_stage_dropped"])  # type: ignore[arg-type]

    def test_empty_strategies_raises(self):
        with pytest.raises(ValueError):
            CompositePruning([])

    def test_single_strategy_equivalent(self):
        msgs = [_msg("user", "q"), _msg("assistant", "")]
        single = DuplicatePruning(protect_recent=0).prune(msgs)
        composite = CompositePruning([DuplicatePruning(protect_recent=0)]).prune(msgs)
        assert single.messages == composite.messages
        assert single.dropped_count == composite.dropped_count


# ---------------------------------------------------------------------------
# PruningResult
# ---------------------------------------------------------------------------


class TestPruningResult:
    def test_defaults(self):
        r = PruningResult(messages=[])
        assert r.messages == []
        assert r.dropped_count == 0
        assert r.metadata == {}

    def test_frozen(self):
        r = PruningResult(messages=[])
        with pytest.raises((AttributeError, TypeError)):
            r.dropped_count = 5  # type: ignore[misc]
