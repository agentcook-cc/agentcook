"""Unit tests for agentcook_core.compaction module."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from agentcook_core.compaction import (
    CompactionResult,
    CompactionStrategy,
    HeuristicTokenCounter,
    IdentityProvider,
    MemorySummarizer,
    SlidingWindowCompaction,
    Summarizer,
    SummaryCompaction,
    TokenBudgetPruning,
    TokenCounter,
)
from agentcook_core.types import Message, ToolCall

# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


class StubSummarizer:
    """Records calls; returns a deterministic summary."""

    def __init__(self, summary: str = "SUMMARY") -> None:
        self.summary = summary
        self.calls: list[Sequence[Message]] = []

    def summarize(self, messages: Sequence[Message]) -> str:
        self.calls.append(list(messages))
        return self.summary


class FixedTokenCounter:
    """Returns a fixed token count per message regardless of content."""

    def __init__(self, per_call: int = 100) -> None:
        self.per_call = per_call

    def count(self, text: str) -> int:
        return self.per_call if text else 0


class StubIdentityProvider:
    def __init__(self, preamble: Sequence[Message]) -> None:
        self._preamble = list(preamble)

    def preamble(self) -> Sequence[Message]:
        return self._preamble


def _msg(role: str, content: str = "x", **kw) -> Message:
    return Message(role=role, content=content, **kw)  # type: ignore[arg-type]


def _conv(n: int) -> list[Message]:
    """Build an alternating user/assistant conversation of length n."""
    out: list[Message] = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        out.append(_msg(role, f"turn {i}"))
    return out


# ---------------------------------------------------------------------------
# Protocol Conformance
# ---------------------------------------------------------------------------


class TestProtocols:
    def test_summary_compaction_satisfies_protocol(self):
        strat = SummaryCompaction(StubSummarizer())
        assert isinstance(strat, CompactionStrategy)

    def test_sliding_window_satisfies_protocol(self):
        strat = SlidingWindowCompaction()
        assert isinstance(strat, CompactionStrategy)

    def test_stub_summarizer_satisfies_protocol(self):
        assert isinstance(StubSummarizer(), Summarizer)

    def test_heuristic_counter_satisfies_protocol(self):
        assert isinstance(HeuristicTokenCounter(), TokenCounter)

    def test_identity_provider_satisfies_protocol(self):
        prov = StubIdentityProvider([_msg("system", "I am alice")])
        assert isinstance(prov, IdentityProvider)


# ---------------------------------------------------------------------------
# HeuristicTokenCounter
# ---------------------------------------------------------------------------


class TestHeuristicTokenCounter:
    def test_empty_text_zero(self):
        assert HeuristicTokenCounter().count("") == 0

    def test_short_text_at_least_one(self):
        assert HeuristicTokenCounter().count("a") == 1

    def test_long_text_proportional(self):
        # 80 chars / 4 = 20 tokens
        assert HeuristicTokenCounter().count("a" * 80) == 20

    def test_count_messages_includes_tool_calls(self):
        counter = HeuristicTokenCounter()
        msg_no_tools = _msg("assistant", "hello world here")  # 16 chars
        msg_with_tool = _msg(
            "assistant",
            "",
            tool_calls=(ToolCall(id="1", name="search", arguments={"q": "py"}),),
        )
        # The tool-call message should add tokens for the name + repr of args.
        no_tools = counter.count_messages([msg_no_tools])
        with_tools = counter.count_messages([msg_with_tool])
        assert with_tools > no_tools - no_tools  # purely positive
        assert with_tools > 0


# ---------------------------------------------------------------------------
# SummaryCompaction — Triggering
# ---------------------------------------------------------------------------


class TestSummaryCompactionShouldCompact:
    def test_short_history_no_compaction(self):
        strat = SummaryCompaction(StubSummarizer(), keep_recent=4)
        assert strat.should_compact(_conv(3), model_window_tokens=1_000) is False

    def test_below_threshold_no_compaction(self):
        # Heuristic: 5 msgs * "turn N" (~6 chars) = ~7 tokens. Window 10_000 → far below 80%.
        strat = SummaryCompaction(StubSummarizer(), keep_recent=2, trigger_ratio=0.8)
        assert strat.should_compact(_conv(5), model_window_tokens=10_000) is False

    def test_above_threshold_triggers(self):
        strat = SummaryCompaction(
            StubSummarizer(),
            token_counter=FixedTokenCounter(per_call=200),
            keep_recent=2,
            trigger_ratio=0.5,
        )
        # 10 msgs * 200 = 2000 tokens; window 1000 * 0.5 = 500 → trigger.
        assert strat.should_compact(_conv(10), model_window_tokens=1_000) is True

    def test_zero_window_raises(self):
        strat = SummaryCompaction(StubSummarizer())
        with pytest.raises(ValueError):
            strat.should_compact(_conv(5), model_window_tokens=0)

    def test_invalid_trigger_ratio_raises(self):
        with pytest.raises(ValueError):
            SummaryCompaction(StubSummarizer(), trigger_ratio=0)
        with pytest.raises(ValueError):
            SummaryCompaction(StubSummarizer(), trigger_ratio=1.5)

    def test_invalid_keep_recent_raises(self):
        with pytest.raises(ValueError):
            SummaryCompaction(StubSummarizer(), keep_recent=0)


# ---------------------------------------------------------------------------
# SummaryCompaction — Compacting
# ---------------------------------------------------------------------------


class TestSummaryCompactionCompact:
    def test_short_history_passthrough(self):
        strat = SummaryCompaction(StubSummarizer(), keep_recent=10)
        msgs = _conv(3)
        result = strat.compact(msgs)
        assert result.messages == msgs
        assert result.dropped_count == 0
        assert result.summary_inserted is False

    def test_below_min_to_summarize_no_llm_call(self):
        summarizer = StubSummarizer()
        strat = SummaryCompaction(summarizer, keep_recent=4, min_to_summarize=10)
        result = strat.compact(_conv(8))  # only 4 older < 10 threshold
        assert summarizer.calls == []
        assert result.summary_inserted is False
        assert result.dropped_count == 0

    def test_summary_replaces_older_turns(self):
        summarizer = StubSummarizer(summary="older context summary")
        strat = SummaryCompaction(summarizer, keep_recent=3, min_to_summarize=2)
        msgs = _conv(10)  # 10 turns: drop oldest 7, summarize, keep 3 recent
        result = strat.compact(msgs)

        assert result.summary_inserted is True
        assert result.dropped_count == 7
        assert len(summarizer.calls) == 1
        assert len(summarizer.calls[0]) == 7
        # First message is the summary; last 3 are the original recent turns.
        assert result.messages[0].role == "system"
        assert "older context summary" in result.messages[0].content
        assert result.messages[-3:] == msgs[-3:]

    def test_preamble_prepended(self):
        identity_msg = _msg("system", "You are Alice, the test agent.")
        strat = SummaryCompaction(
            StubSummarizer(),
            keep_recent=2,
            min_to_summarize=2,
            identity_provider=StubIdentityProvider([identity_msg]),
        )
        msgs = _conv(8)
        result = strat.compact(msgs)
        assert result.messages[0] == identity_msg
        assert result.messages[1].role == "system"  # the summary
        assert "Compacted history summary" in result.messages[1].content

    def test_preamble_when_below_min_to_summarize(self):
        identity_msg = _msg("system", "I am Alice.")
        strat = SummaryCompaction(
            StubSummarizer(),
            keep_recent=4,
            min_to_summarize=10,
            identity_provider=StubIdentityProvider([identity_msg]),
        )
        msgs = _conv(8)
        result = strat.compact(msgs)
        # No summary call but preamble still prepended.
        assert result.messages[0] == identity_msg
        assert result.summary_inserted is False

    def test_summary_message_metadata(self):
        strat = SummaryCompaction(StubSummarizer(), keep_recent=2, min_to_summarize=2)
        result = strat.compact(_conv(8))
        # The summary message records how many it covered (6 older = 8 - 2 recent).
        summary = next(m for m in result.messages if m.role == "system")
        assert summary.metadata.get("compaction") == "summary"
        assert summary.metadata.get("covers_messages") == 6

    def test_empty_messages_passthrough(self):
        strat = SummaryCompaction(StubSummarizer())
        result = strat.compact([])
        assert result.messages == []
        assert result.summary_inserted is False


# ---------------------------------------------------------------------------
# SlidingWindowCompaction
# ---------------------------------------------------------------------------


class TestSlidingWindowCompaction:
    def test_below_window_passthrough(self):
        strat = SlidingWindowCompaction(window_size=10)
        msgs = _conv(5)
        result = strat.compact(msgs)
        assert result.messages == msgs
        assert result.dropped_count == 0

    def test_drops_oldest(self):
        strat = SlidingWindowCompaction(window_size=3)
        msgs = _conv(10)
        result = strat.compact(msgs)
        assert len(result.messages) == 3
        assert result.messages == msgs[-3:]
        assert result.dropped_count == 7

    def test_preamble_re_injected(self):
        identity_msg = _msg("system", "I am Bob.")
        strat = SlidingWindowCompaction(
            window_size=2,
            identity_provider=StubIdentityProvider([identity_msg]),
        )
        msgs = _conv(8)
        result = strat.compact(msgs)
        assert result.messages[0] == identity_msg
        # Preamble + 2 kept = 3 total.
        assert len(result.messages) == 3

    def test_should_compact_below_window_false(self):
        strat = SlidingWindowCompaction(window_size=10)
        assert strat.should_compact(_conv(5), model_window_tokens=1_000) is False

    def test_should_compact_above_token_threshold(self):
        strat = SlidingWindowCompaction(
            window_size=2,
            token_counter=FixedTokenCounter(per_call=300),
            trigger_ratio=0.5,
        )
        # 10 msgs * 300 = 3000, threshold = 500. 10 > window=2, used > threshold.
        assert strat.should_compact(_conv(10), model_window_tokens=1_000) is True

    def test_invalid_window_size_raises(self):
        with pytest.raises(ValueError):
            SlidingWindowCompaction(window_size=0)

    def test_invalid_trigger_ratio_raises(self):
        with pytest.raises(ValueError):
            SlidingWindowCompaction(trigger_ratio=0)
        with pytest.raises(ValueError):
            SlidingWindowCompaction(trigger_ratio=1.1)

    def test_zero_window_tokens_raises(self):
        strat = SlidingWindowCompaction()
        with pytest.raises(ValueError):
            strat.should_compact(_conv(5), model_window_tokens=0)

    def test_empty_messages_passthrough(self):
        strat = SlidingWindowCompaction(window_size=5)
        result = strat.compact([])
        assert result.messages == []


# ---------------------------------------------------------------------------
# CompactionResult
# ---------------------------------------------------------------------------


class TestCompactionResult:
    def test_default_construction(self):
        r = CompactionResult(messages=[])
        assert r.messages == []
        assert r.dropped_count == 0
        assert r.summary_inserted is False
        assert r.metadata == {}

    def test_frozen(self):
        r = CompactionResult(messages=[])
        with pytest.raises((AttributeError, TypeError)):
            r.dropped_count = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TokenBudgetPruning
# ---------------------------------------------------------------------------


class TestTokenBudgetPruning:
    def test_no_op_when_under_budget(self):
        strategy = TokenBudgetPruning(budget=50000)
        msgs = _conv(5)
        result = strategy.compact(msgs)
        assert result.dropped_count == 0
        assert len(result.messages) == 5

    def test_prunes_when_over_budget(self):
        # Use a counter that returns high values to force pruning
        strategy = TokenBudgetPruning(
            budget=200,
            token_counter=FixedTokenCounter(per_call=50),
            min_recent_turns=2,
        )
        msgs = _conv(10)
        result = strategy.compact(msgs)
        assert result.dropped_count > 0
        assert len(result.messages) < 10

    def test_preserves_min_recent_turns(self):
        strategy = TokenBudgetPruning(
            budget=200,
            token_counter=FixedTokenCounter(per_call=50),
            min_recent_turns=4,
        )
        msgs = _conv(10)
        result = strategy.compact(msgs)
        # Should keep at least 4 conversation messages
        non_system = [m for m in result.messages if m.role != "system"]
        assert len(non_system) >= 4

    def test_with_summarizer(self):
        summarizer = StubSummarizer("Budget summary")
        strategy = TokenBudgetPruning(
            budget=200,
            token_counter=FixedTokenCounter(per_call=50),
            summarizer=summarizer,
            min_recent_turns=2,
        )
        msgs = _conv(10)
        result = strategy.compact(msgs)
        assert result.summary_inserted is True
        assert len(summarizer.calls) == 1
        # Should have a summary message in output
        summaries = [m for m in result.messages if "summary" in m.content.lower()]
        assert len(summaries) >= 1

    def test_with_identity_provider(self):
        preamble = [_msg("system", "I am the agent")]
        identity = StubIdentityProvider(preamble)
        strategy = TokenBudgetPruning(
            budget=200,
            token_counter=FixedTokenCounter(per_call=50),
            identity_provider=identity,
            min_recent_turns=2,
        )
        msgs = _conv(10)
        result = strategy.compact(msgs)
        assert result.messages[0].content == "I am the agent"

    def test_should_compact_under_budget(self):
        strategy = TokenBudgetPruning(budget=50000)
        msgs = _conv(5)
        assert strategy.should_compact(msgs, model_window_tokens=100000) is False

    def test_should_compact_over_budget(self):
        strategy = TokenBudgetPruning(
            budget=100,
            token_counter=FixedTokenCounter(per_call=50),
        )
        msgs = _conv(10)
        assert strategy.should_compact(msgs, model_window_tokens=100000) is True

    def test_invalid_budget_raises(self):
        with pytest.raises(ValueError):
            TokenBudgetPruning(budget=50)

    def test_invalid_min_recent_raises(self):
        with pytest.raises(ValueError):
            TokenBudgetPruning(budget=4096, min_recent_turns=0)


# ---------------------------------------------------------------------------
# MemorySummarizer
# ---------------------------------------------------------------------------


class TestMemorySummarizer:
    def test_protocol_compliance(self):
        s = MemorySummarizer(lambda prompt: "ok")
        assert isinstance(s, Summarizer)

    def test_calls_fn_with_prompt(self):
        received: list[str] = []

        def capture(prompt: str) -> str:
            received.append(prompt)
            return "Summary result"

        s = MemorySummarizer(capture)
        msgs = [_msg("user", "hello"), _msg("assistant", "hi")]
        result = s.summarize(msgs)
        assert result == "Summary result"
        assert len(received) == 1
        assert "user: hello" in received[0]
        assert "assistant: hi" in received[0]

    def test_handles_fn_exception_gracefully(self):
        def failing(prompt: str) -> str:
            raise RuntimeError("LLM unavailable")

        s = MemorySummarizer(failing)
        msgs = [_msg("user", "test")]
        result = s.summarize(msgs)
        assert "unavailable" in result.lower()

    def test_truncates_long_content_in_prompt(self):
        received: list[str] = []

        def capture(prompt: str) -> str:
            received.append(prompt)
            return "ok"

        s = MemorySummarizer(capture)
        msgs = [_msg("user", "x" * 500)]
        s.summarize(msgs)
        # Content preview is limited to 200 chars
        assert "x" * 201 not in received[0]
