"""Context Management — message-history compaction strategies.

Long-running agent conversations grow past every model's context window.
This module provides pluggable strategies that shrink message history while
preserving the load-bearing parts: Identity / Soul preamble + the most
recent turns.

Design:
- stdlib-only. No provider/model SDK imports — keeps ``agentcook-core``
  installable in any environment.
- ``Summarizer`` Protocol — injected callable that condenses a chunk of
  messages into a single summary string. Implementations typically wrap
  ``model_router`` + a cheap model, but the core never knows that.
- ``TokenCounter`` Protocol — injected; defaults to a 4-chars-per-token
  heuristic so this module works with zero extra dependencies. Plug in a
  real tokenizer (e.g. ``tiktoken``) for accuracy.
- ``IdentityProvider`` Protocol — supplies the frozen Identity / Soul
  preamble messages to re-prepend after compaction.

Two strategies ship today:

- :class:`SummaryCompaction` — older turns become one summarized system
  message; recent turns pass through unchanged.
- :class:`SlidingWindowCompaction` — drop oldest turns past a fixed
  window; preamble is re-injected.

Designed to compose: a caller may run pruning first (drop noise), then
compaction (shrink residue), then re-prepend Identity. Each strategy is
deterministic given the same inputs and injected dependencies.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from agentcook_core.tracing import get_tracer
from agentcook_core.types import Message

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocols (injectable boundaries)
# ---------------------------------------------------------------------------


@runtime_checkable
class TokenCounter(Protocol):
    """Counts tokens in arbitrary text.

    The default :class:`HeuristicTokenCounter` is good enough for trigger
    decisions but undercounts CJK / overcounts code. Plug in a real
    tokenizer at the application boundary if accuracy matters.
    """

    def count(self, text: str) -> int:
        """Return the token count for *text*."""
        ...


@runtime_checkable
class Summarizer(Protocol):
    """Condenses a window of messages into a single text summary.

    Implementations typically delegate to a cheap LLM (via
    ``model_router``). The summary is what :class:`SummaryCompaction`
    inserts in place of the dropped turns.
    """

    def summarize(self, messages: Sequence[Message]) -> str:
        """Return a concise summary covering the salient facts of *messages*."""
        ...


@runtime_checkable
class IdentityProvider(Protocol):
    """Yields the immutable preamble re-injected after compaction.

    Typically the agent's Identity card and Soul traits, expressed as
    one or more ``system`` messages. Returned messages are prepended in
    the order yielded.
    """

    def preamble(self) -> Sequence[Message]:
        """Return the messages to re-prepend after compaction."""
        ...


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


class HeuristicTokenCounter:
    """Cheap default — assumes ~4 chars per token across roles.

    Counts both ``content`` and the JSON form of any tool calls. Off by a
    factor of ~2x for CJK; replace with a real tokenizer if it matters.
    """

    _CHARS_PER_TOKEN = 4

    def count(self, text: str) -> int:
        if not text:
            return 0
        return max(1, len(text) // self._CHARS_PER_TOKEN)

    def count_messages(self, messages: Iterable[Message]) -> int:
        total = 0
        for msg in messages:
            total += self.count(msg.content)
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    total += self.count(tc.name)
                    total += self.count(str(tc.arguments))
        return total


class _NullIdentityProvider:
    """Default — no preamble. Used when the caller doesn't inject one."""

    def preamble(self) -> Sequence[Message]:
        return ()


# ---------------------------------------------------------------------------
# Strategy Protocol
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CompactionResult:
    """Outcome of a single :meth:`CompactionStrategy.compact` call."""

    messages: list[Message]
    dropped_count: int = 0
    summary_inserted: bool = False
    metadata: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class CompactionStrategy(Protocol):
    """Pluggable compaction policy.

    Implementations decide *when* to compact (``should_compact``) and
    *how* to compact (``compact``). Calling ``compact`` on input that
    doesn't need compaction MUST be a safe no-op — return the messages
    unchanged with ``dropped_count=0``.
    """

    def should_compact(
        self,
        messages: Sequence[Message],
        model_window_tokens: int,
    ) -> bool:
        """Return True if *messages* should be compacted before next call."""
        ...

    def compact(self, messages: Sequence[Message]) -> CompactionResult:
        """Return a shrunk version of *messages* (or the same list if no-op)."""
        ...


# ---------------------------------------------------------------------------
# SummaryCompaction
# ---------------------------------------------------------------------------


class SummaryCompaction:
    """Replace older turns with a single summarized ``system`` message.

    Triggers when ``count_messages(messages) >= trigger_ratio * window``.
    Keeps the newest ``keep_recent`` turns verbatim; everything older is
    handed to :class:`Summarizer` and the resulting summary is inserted
    as the first ``system`` message after the preamble.

    Args:
        summarizer: Required. The text-condensation backend.
        token_counter: Defaults to :class:`HeuristicTokenCounter`.
        identity_provider: Optional preamble injector.
        trigger_ratio: Compact when used tokens exceed this fraction of
            the model window. Default ``0.8``.
        keep_recent: Number of newest turns to preserve verbatim.
            Default ``6``.
        min_to_summarize: Don't bother summarizing fewer than this many
            messages — it's not worth the LLM call. Default ``4``.
    """

    def __init__(
        self,
        summarizer: Summarizer,
        *,
        token_counter: TokenCounter | None = None,
        identity_provider: IdentityProvider | None = None,
        trigger_ratio: float = 0.8,
        keep_recent: int = 6,
        min_to_summarize: int = 4,
    ) -> None:
        if not 0.0 < trigger_ratio <= 1.0:
            raise ValueError("trigger_ratio must be in (0, 1]")
        if keep_recent < 1:
            raise ValueError("keep_recent must be >= 1")
        if min_to_summarize < 1:
            raise ValueError("min_to_summarize must be >= 1")

        self._summarizer = summarizer
        self._counter = token_counter or HeuristicTokenCounter()
        self._identity = identity_provider or _NullIdentityProvider()
        self._trigger_ratio = trigger_ratio
        self._keep_recent = keep_recent
        self._min_to_summarize = min_to_summarize

    def should_compact(
        self,
        messages: Sequence[Message],
        model_window_tokens: int,
    ) -> bool:
        if model_window_tokens <= 0:
            raise ValueError("model_window_tokens must be > 0")
        if len(messages) <= self._keep_recent:
            return False
        used = _count(self._counter, messages)
        threshold = int(model_window_tokens * self._trigger_ratio)
        return used >= threshold

    def compact(self, messages: Sequence[Message]) -> CompactionResult:
        with get_tracer().start_span(
            "compaction.summary",
            attributes={
                "agentcook.compaction.input_count": len(messages),
                "agentcook.compaction.keep_recent": self._keep_recent,
                "agentcook.compaction.min_to_summarize": self._min_to_summarize,
            },
        ) as span:
            msg_list = list(messages)

            if len(msg_list) <= self._keep_recent:
                span.set_attribute("agentcook.compaction.action", "noop_short")
                return CompactionResult(messages=msg_list)

            recent = msg_list[-self._keep_recent :]
            older = msg_list[: -self._keep_recent]

            if len(older) < self._min_to_summarize:
                span.set_attribute("agentcook.compaction.action", "preamble_only")
                return CompactionResult(
                    messages=[*self._identity.preamble(), *older, *recent],
                    dropped_count=0,
                )

            summary_text = self._summarizer.summarize(older)
            summary_msg = Message(
                role="system",
                content=f"[Compacted history summary]\n{summary_text}",
                metadata={"compaction": "summary", "covers_messages": len(older)},
            )

            compacted = [*self._identity.preamble(), summary_msg, *recent]
            span.set_attribute("agentcook.compaction.action", "summarized")
            span.set_attribute("agentcook.compaction.dropped", len(older))
            logger.debug(
                "SummaryCompaction: %d older messages -> 1 summary (kept %d recent)",
                len(older),
                len(recent),
            )
            return CompactionResult(
                messages=compacted,
                dropped_count=len(older),
                summary_inserted=True,
            )


# ---------------------------------------------------------------------------
# SlidingWindowCompaction
# ---------------------------------------------------------------------------


class SlidingWindowCompaction:
    """Keep newest ``window_size`` turns; drop the rest. Re-prepend preamble.

    Cheaper than :class:`SummaryCompaction` (no LLM call). Useful when:
    - The summarizer is unavailable or too expensive.
    - Older context is genuinely irrelevant (e.g. transient tool noise).
    - You want a deterministic fallback path.

    Identity/Soul are re-injected so the model never loses persona, even
    if the window slides past the original system prompt.
    """

    def __init__(
        self,
        *,
        window_size: int = 20,
        token_counter: TokenCounter | None = None,
        identity_provider: IdentityProvider | None = None,
        trigger_ratio: float = 0.85,
    ) -> None:
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        if not 0.0 < trigger_ratio <= 1.0:
            raise ValueError("trigger_ratio must be in (0, 1]")

        self._window = window_size
        self._counter = token_counter or HeuristicTokenCounter()
        self._identity = identity_provider or _NullIdentityProvider()
        self._trigger_ratio = trigger_ratio

    def should_compact(
        self,
        messages: Sequence[Message],
        model_window_tokens: int,
    ) -> bool:
        if model_window_tokens <= 0:
            raise ValueError("model_window_tokens must be > 0")
        if len(messages) <= self._window:
            return False
        used = _count(self._counter, messages)
        threshold = int(model_window_tokens * self._trigger_ratio)
        return used >= threshold

    def compact(self, messages: Sequence[Message]) -> CompactionResult:
        with get_tracer().start_span(
            "compaction.sliding_window",
            attributes={
                "agentcook.compaction.input_count": len(messages),
                "agentcook.compaction.window_size": self._window,
            },
        ) as span:
            msg_list = list(messages)
            if len(msg_list) <= self._window:
                span.set_attribute("agentcook.compaction.action", "noop_short")
                return CompactionResult(messages=msg_list)

            kept = msg_list[-self._window :]
            dropped = len(msg_list) - len(kept)
            compacted = [*self._identity.preamble(), *kept]
            span.set_attribute("agentcook.compaction.dropped", dropped)
            logger.debug(
                "SlidingWindowCompaction: dropped %d, kept %d (window=%d)",
                dropped,
                len(kept),
                self._window,
            )
            return CompactionResult(
                messages=compacted,
                dropped_count=dropped,
            )


# ---------------------------------------------------------------------------
# TokenBudgetPruning
# ---------------------------------------------------------------------------


class TokenBudgetPruning:
    """Prune messages to fit within a strict token budget.

    Preserves (in priority order):
    1. Identity/Soul preamble (always kept)
    2. Most recent ``min_recent_turns`` messages
    3. Earlier messages until budget exhausted

    If a :class:`Summarizer` is provided, pruned content is summarized
    into a single system message. Otherwise pruned content is simply dropped.

    Args:
        budget: Maximum token count for the output messages.
        token_counter: Injected token counter.
        summarizer: Optional summarizer for pruned content.
        identity_provider: Preamble injector.
        min_recent_turns: Minimum number of recent turns to preserve
            regardless of budget.
    """

    def __init__(
        self,
        budget: int = 4096,
        *,
        token_counter: TokenCounter | None = None,
        summarizer: Summarizer | None = None,
        identity_provider: IdentityProvider | None = None,
        min_recent_turns: int = 4,
    ) -> None:
        if budget < 100:
            raise ValueError("budget must be >= 100 tokens")
        if min_recent_turns < 1:
            raise ValueError("min_recent_turns must be >= 1")
        self._budget = budget
        self._counter = token_counter or HeuristicTokenCounter()
        self._identity = identity_provider or _NullIdentityProvider()
        self._summarizer = summarizer
        self._min_recent = min_recent_turns

    def should_compact(
        self,
        messages: Sequence[Message],
        model_window_tokens: int,
    ) -> bool:
        """Return True if messages exceed the budget."""
        used = _count(self._counter, messages)
        return used > self._budget

    def compact(self, messages: Sequence[Message]) -> CompactionResult:
        """Prune messages to fit within budget, preserving recent turns."""
        with get_tracer().start_span(
            "compaction.token_budget",
            attributes={
                "agentcook.compaction.input_count": len(messages),
                "agentcook.compaction.budget": self._budget,
            },
        ) as span:
            msg_list = list(messages)
            total_tokens = _count(self._counter, msg_list)

            if total_tokens <= self._budget:
                span.set_attribute("agentcook.compaction.action", "noop_under_budget")
                return CompactionResult(messages=msg_list)

            preamble = list(self._identity.preamble())
            preamble_tokens = _count(self._counter, preamble)
            remaining_budget = self._budget - preamble_tokens

            # Always keep at least min_recent_turns from the end
            recent: list[Message] = []
            recent_tokens = 0
            for msg in reversed(msg_list):
                msg_tok = _count(self._counter, [msg])
                if len(recent) < self._min_recent or recent_tokens + msg_tok <= remaining_budget:
                    recent.insert(0, msg)
                    recent_tokens += msg_tok
                    if len(recent) >= self._min_recent and recent_tokens >= remaining_budget:
                        break
                else:
                    break

            # Determine pruned messages
            kept_count = len(recent)
            pruned = msg_list[:len(msg_list) - kept_count]

            # Summarize pruned if summarizer available
            summary_msg: list[Message] = []
            if pruned and self._summarizer:
                summary_text = self._summarizer.summarize(pruned)
                summary_msg = [
                    Message(
                        role="system",
                        content=f"[Context summary — {len(pruned)} messages pruned]\n{summary_text}",
                        metadata={"compaction": "token_budget_summary", "covers_messages": len(pruned)},
                    )
                ]

            compacted = [*preamble, *summary_msg, *recent]
            span.set_attribute("agentcook.compaction.action", "pruned")
            span.set_attribute("agentcook.compaction.dropped", len(pruned))
            logger.debug(
                "TokenBudgetPruning: dropped %d, kept %d (budget=%d)",
                len(pruned),
                kept_count,
                self._budget,
            )
            return CompactionResult(
                messages=compacted,
                dropped_count=len(pruned),
                summary_inserted=bool(summary_msg),
                metadata={"strategy": "token_budget", "budget": self._budget},
            )


# ---------------------------------------------------------------------------
# MemorySummarizer
# ---------------------------------------------------------------------------


class MemorySummarizer:
    """Summarizer backed by an injected LLM callable.

    Wraps a ``summarize_fn`` that takes a prompt string and returns
    summary text. This keeps the compaction module free of LLM provider
    dependencies — the caller injects the actual LLM call.

    Args:
        summarize_fn: Callable ``(prompt: str) -> str`` that generates summaries.
    """

    def __init__(self, summarize_fn: object) -> None:
        self._fn = summarize_fn

    def summarize(self, messages: Sequence[Message]) -> str:
        lines: list[str] = []
        for msg in messages:
            content_preview = msg.content[:200] if msg.content else ""
            lines.append(f"{msg.role}: {content_preview}")

        prompt = (
            "Summarize the following conversation in 2-3 concise sentences, "
            "preserving key facts, decisions, and action items:\n\n"
            + "\n".join(lines)
        )

        try:
            result = self._fn(prompt)  # type: ignore[operator]
            return str(result)
        except Exception as exc:
            logger.warning("MemorySummarizer failed: %s", exc)
            return f"[Summary unavailable: {len(messages)} messages pruned]"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _count(counter: TokenCounter, messages: Sequence[Message]) -> int:
    if isinstance(counter, HeuristicTokenCounter):
        return counter.count_messages(messages)
    total = 0
    for msg in messages:
        total += counter.count(msg.content)
        if msg.tool_calls:
            for tc in msg.tool_calls:
                total += counter.count(tc.name)
                total += counter.count(str(tc.arguments))
    return total


__all__ = [
    "CompactionResult",
    "CompactionStrategy",
    "HeuristicTokenCounter",
    "IdentityProvider",
    "MemorySummarizer",
    "SlidingWindowCompaction",
    "SummaryCompaction",
    "Summarizer",
    "TokenBudgetPruning",
    "TokenCounter",
]
