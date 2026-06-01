"""Context Management — message-history pruning strategies.

Pruning trims *individual* turns from a conversation that don't pull
their weight: low-relevance side-quests, repeat tool calls, empty
assistant turns. Distinct from compaction (which summarizes a window):

- **Compaction**  reduces N old turns → 1 summary. Lossy by design.
- **Pruning**     drops noise turn-by-turn. Each kept turn is verbatim.

Run pruning before compaction to maximize signal density in what
survives. Strategies are composable — chain ``DuplicatePruning`` →
``RelevancePruning`` to drop both noise and irrelevance.

Design:
- stdlib-only.
- ``RelevancePruning`` reuses the :class:`agentcook_core.memory.EmbeddingProvider`
  Protocol — no separate embedding contract, no double maintenance.
- All strategies preserve ``system`` messages and the trailing ``protect_recent``
  turns by default. The model needs persona + the immediate conversation
  state to function, so those are off-limits.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from agentcook_core.memory import EmbeddingProvider
from agentcook_core.tracing import get_tracer
from agentcook_core.types import Message, ToolCall

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Strategy Protocol
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PruningResult:
    """Outcome of a single :meth:`PruningStrategy.prune` call."""

    messages: list[Message]
    dropped_count: int = 0
    metadata: dict[str, object] = field(default_factory=dict)


@runtime_checkable
class PruningStrategy(Protocol):
    """Pluggable pruning policy.

    Implementations decide *which* turns to drop. Calling ``prune`` on
    input that doesn't need pruning MUST be a safe no-op.
    """

    def prune(self, messages: Sequence[Message]) -> PruningResult:
        """Return *messages* with low-value turns removed."""
        ...


# ---------------------------------------------------------------------------
# RelevancePruning
# ---------------------------------------------------------------------------


class RelevancePruning:
    """Drop low-relevance turns based on embedding similarity + time decay.

    For each candidate message, score = ``similarity(msg, anchor) *
    decay(age)``. Messages scoring below ``min_score`` are dropped.

    The *anchor* is the most recent ``user`` message by default — the
    assumption being "what's relevant right now is what's similar to
    what the user just asked." Override ``anchor_text`` for explicit
    control.

    Args:
        embedder: Required. :class:`EmbeddingProvider` instance.
        min_score: Drop messages scoring below this. Default ``0.3``.
        protect_recent: Last K turns are never pruned. Default ``4``.
        decay_half_life_turns: Each ``half_life`` turns of age multiplies
            the score by 0.5. Default ``20``. Set very large to disable
            decay.
        anchor_text: If provided, used as the relevance anchor instead
            of inferring from the message list.
    """

    def __init__(
        self,
        embedder: EmbeddingProvider,
        *,
        min_score: float = 0.3,
        protect_recent: int = 4,
        decay_half_life_turns: int = 20,
        anchor_text: str | None = None,
    ) -> None:
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score must be in [0, 1]")
        if protect_recent < 0:
            raise ValueError("protect_recent must be >= 0")
        if decay_half_life_turns < 1:
            raise ValueError("decay_half_life_turns must be >= 1")

        self._embedder = embedder
        self._min_score = min_score
        self._protect_recent = protect_recent
        self._half_life = decay_half_life_turns
        self._anchor_text = anchor_text

    def prune(self, messages: Sequence[Message]) -> PruningResult:
        msg_list = list(messages)
        with get_tracer().start_span(
            "pruning.relevance",
            attributes={
                "agentcook.pruning.input_count": len(msg_list),
                "agentcook.pruning.min_score": self._min_score,
                "agentcook.pruning.protect_recent": self._protect_recent,
            },
        ) as span:
            if not msg_list:
                return PruningResult(messages=[])

            anchor = self._anchor_text or _last_user_text(msg_list)
            if not anchor:
                # No anchor → cannot score. Bail safely (no-op).
                span.set_attribute("agentcook.pruning.action", "no_anchor")
                logger.debug("RelevancePruning: no anchor text, skipping")
                return PruningResult(messages=msg_list)

            anchor_vec = self._embedder.embed(anchor)
            protect_floor = max(0, len(msg_list) - self._protect_recent)

            kept: list[Message] = []
            dropped = 0
            for idx, msg in enumerate(msg_list):
                # Always keep system messages + protected recent tail.
                if msg.role == "system" or idx >= protect_floor:
                    kept.append(msg)
                    continue

                # tool messages are scored by their content (the result text),
                # which is usually informative enough to embed.
                text = msg.content
                if not text:
                    # Empty content with no tool_calls is dead weight; drop.
                    # If it has tool_calls, keep — DuplicatePruning handles those.
                    if msg.tool_calls:
                        kept.append(msg)
                    else:
                        dropped += 1
                    continue

                msg_vec = self._embedder.embed(text)
                similarity = self._embedder.similarity(anchor_vec, msg_vec)

                age_turns = len(msg_list) - 1 - idx
                decay = 0.5 ** (age_turns / self._half_life)
                score = similarity * decay

                if score >= self._min_score:
                    kept.append(msg)
                else:
                    dropped += 1

            span.set_attribute("agentcook.pruning.dropped", dropped)
            if dropped:
                logger.debug(
                    "RelevancePruning: dropped %d/%d (min_score=%.2f, half_life=%d)",
                    dropped,
                    len(msg_list),
                    self._min_score,
                    self._half_life,
                )
            return PruningResult(messages=kept, dropped_count=dropped)


# ---------------------------------------------------------------------------
# DuplicatePruning
# ---------------------------------------------------------------------------


class DuplicatePruning:
    """Drop redundant / empty turns.

    Targets three specific noise patterns observed in real agent
    transcripts:

    1. **Repeat tool calls** — the same ``(name, arguments)`` pair
       emitted twice in a row, typically from a model retrying on its
       own. Keep the first; drop the duplicate. The corresponding tool
       result message (if any) is kept — only the duplicate *call* is
       dropped.
    2. **Empty assistant turns** — ``role=assistant`` with empty
       ``content`` AND no ``tool_calls``. Pure noise.
    3. **Adjacent identical user messages** — same content twice in a
       row from the user (often a UI double-submit). Keep the latest.

    System messages are never touched. Recent ``protect_recent`` turns
    are never touched.
    """

    def __init__(self, *, protect_recent: int = 2) -> None:
        if protect_recent < 0:
            raise ValueError("protect_recent must be >= 0")
        self._protect_recent = protect_recent

    def prune(self, messages: Sequence[Message]) -> PruningResult:
        msg_list = list(messages)
        with get_tracer().start_span(
            "pruning.duplicate",
            attributes={
                "agentcook.pruning.input_count": len(msg_list),
                "agentcook.pruning.protect_recent": self._protect_recent,
            },
        ) as span:
            if len(msg_list) < 2:
                return PruningResult(messages=msg_list)

            protect_floor = max(0, len(msg_list) - self._protect_recent)
            kept: list[Message] = []
            dropped = 0
            last_tool_call_sig: str | None = None
            last_user_content: str | None = None

            for idx, msg in enumerate(msg_list):
                # Always keep system + protected tail.
                if msg.role == "system" or idx >= protect_floor:
                    kept.append(msg)
                    # Reset duplicate trackers when crossing into protect zone.
                    last_tool_call_sig = None
                    last_user_content = None
                    continue

                # Empty assistant turn with no tool calls → drop.
                if msg.role == "assistant" and not msg.content and not msg.tool_calls:
                    dropped += 1
                    continue

                # Duplicate user message (back-to-back, identical content) → drop earlier.
                if msg.role == "user" and msg.content == last_user_content:
                    dropped += 1
                    continue
                if msg.role == "user":
                    last_user_content = msg.content
                    last_tool_call_sig = None
                    kept.append(msg)
                    continue

                # Repeat tool call → drop. Compare assistant turns that *only*
                # carry tool_calls (no real text content), to avoid eating
                # legitimate retries that include a follow-up explanation.
                if msg.role == "assistant" and msg.tool_calls and not msg.content:
                    sig = _tool_call_signature(msg.tool_calls)
                    if sig == last_tool_call_sig:
                        dropped += 1
                        continue
                    last_tool_call_sig = sig
                    kept.append(msg)
                    continue

                # Anything else passes through; reset duplicate trackers.
                last_tool_call_sig = None
                last_user_content = None
                kept.append(msg)

            span.set_attribute("agentcook.pruning.dropped", dropped)
            if dropped:
                logger.debug("DuplicatePruning: dropped %d/%d", dropped, len(msg_list))
            return PruningResult(messages=kept, dropped_count=dropped)


# ---------------------------------------------------------------------------
# Composite
# ---------------------------------------------------------------------------


class CompositePruning:
    """Run multiple strategies in order; ``dropped_count`` is summed."""

    def __init__(self, strategies: Sequence[PruningStrategy]) -> None:
        if not strategies:
            raise ValueError("CompositePruning requires at least one strategy")
        self._strategies = tuple(strategies)

    def prune(self, messages: Sequence[Message]) -> PruningResult:
        with get_tracer().start_span(
            "pruning.composite",
            attributes={
                "agentcook.pruning.input_count": len(messages),
                "agentcook.pruning.stage_count": len(self._strategies),
            },
        ) as span:
            current = list(messages)
            total_dropped = 0
            per_stage: list[int] = []
            for strat in self._strategies:
                result = strat.prune(current)
                current = result.messages
                total_dropped += result.dropped_count
                per_stage.append(result.dropped_count)
            span.set_attribute("agentcook.pruning.total_dropped", total_dropped)
            return PruningResult(
                messages=current,
                dropped_count=total_dropped,
                metadata={"per_stage_dropped": per_stage},
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _last_user_text(messages: Sequence[Message]) -> str:
    for msg in reversed(messages):
        if msg.role == "user" and msg.content:
            return msg.content
    return ""


def _tool_call_signature(tool_calls: Sequence[ToolCall]) -> str:
    parts = []
    for tc in tool_calls:
        # Sort args for stable signature regardless of dict ordering.
        args_repr = repr(sorted(tc.arguments.items())) if tc.arguments else "{}"
        parts.append(f"{tc.name}|{args_repr}")
    return "||".join(parts)


__all__ = [
    "CompositePruning",
    "DuplicatePruning",
    "PruningResult",
    "PruningStrategy",
    "RelevancePruning",
]
