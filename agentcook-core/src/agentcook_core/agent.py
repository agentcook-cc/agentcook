"""The agent loop — harness dimension #1.

An *agent* here is the classic Reason → Act → Observe loop:

1. send the conversation + tool definitions to the model;
2. if the model asks for tools, run them (concurrently, each under a
   timeout) and append their results;
3. repeat until the model answers without tool calls or ``max_turns``
   is reached.

This module is engine-agnostic and stdlib-only. It talks to models only
through :class:`~agentcook_core.protocols.LLMProviderProtocol` and to
tools only through :class:`~agentcook_core.protocols.ToolProtocol`, so
the same loop drives OpenAI, Anthropic, Qwen, the offline mock provider,
MCP tools and sub-agents.

The runner is *streaming-first*: :meth:`AgentRunner.run_stream` yields
typed :data:`AgentEvent` values (text deltas, tool calls, tool results,
per-turn usage, completion) that map 1:1 onto the SSE frames the chat
API emits. :meth:`AgentRunner.run` is a thin "drain the stream" wrapper
for callers that only want the final answer.

Production concerns handled here rather than left to each caller:

- **Context window** — :class:`ContextWindow` trims history to the
  model's window *by whole exchanges*, so an assistant ``tool_calls``
  message is never separated from its ``tool`` results (both OpenAI and
  Anthropic reject such transcripts).
- **Tool safety** — unknown tools, invalid arguments, exceptions and
  timeouts all become ``ERROR:`` tool results the model can recover
  from; a tool can never crash the run. :class:`RunHooks.before_tool_call`
  lets a policy veto calls (see :class:`ToolPolicy`).
- **Output hygiene** — tool output is truncated with an explicit marker.
- **Cancellation** — closing the event stream (client disconnect)
  cancels in-flight tool tasks.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, ClassVar

from agentcook_core.protocols import LLMProviderProtocol, ToolProtocol
from agentcook_core.tokens import estimate_message_tokens, estimate_tokens
from agentcook_core.tools import (
    RunContext,
    Toolset,
    _reset_run_context,
    _set_run_context,
    current_run_context,
    render_tool_output,
)
from agentcook_core.tracing import get_tracer
from agentcook_core.types import (
    AgentResponse,
    Message,
    TokenUsage,
    ToolCall,
    ToolResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Agent:
    """Declarative agent definition (what the agent *is*, not how it runs).

    The model provider is supplied by the :class:`AgentRunner` at run
    time so the same definition can be served by different providers
    (e.g. quota-based downgrade, fallback chains, offline mock).
    """

    name: str
    instructions: str = ""
    description: str = ""
    tools: tuple[ToolProtocol, ...] = ()
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    max_turns: int = 8
    tool_timeout: float = 30.0
    max_tool_output_chars: int = 8_000
    parallel_tool_calls: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Agent.name must not be empty")
        if self.max_turns < 1:
            raise ValueError("Agent.max_turns must be >= 1")
        if self.tool_timeout <= 0:
            raise ValueError("Agent.tool_timeout must be > 0")
        if not isinstance(self.tools, tuple):
            object.__setattr__(self, "tools", tuple(self.tools))
        # Validate names / duplicates eagerly — fail at definition time,
        # not on the first request.
        Toolset(self.tools)

    def with_tools(self, *extra: ToolProtocol) -> Agent:
        """Return a copy with *extra* tools layered on (same name wins)."""
        merged = Toolset(self.tools).merged(extra)
        return dataclasses.replace(self, tools=tuple(merged))

    def with_instructions(self, instructions: str) -> Agent:
        return dataclasses.replace(self, instructions=instructions)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def _usage_dict(usage: TokenUsage) -> dict[str, int]:
    return {
        "input_tokens": usage.input,
        "output_tokens": usage.output,
        "cached_tokens": usage.cached,
        "total_tokens": usage.total,
    }


def _call_dict(call: ToolCall) -> dict[str, Any]:
    return {"id": call.id, "name": call.name, "arguments": call.arguments}


@dataclass(frozen=True, slots=True)
class RunStarted:
    type: ClassVar[str] = "run_started"
    run_id: str
    agent: str

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "run_id": self.run_id, "agent": self.agent}


@dataclass(frozen=True, slots=True)
class TextDelta:
    type: ClassVar[str] = "text_delta"
    text: str
    turn: int

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "text": self.text, "turn": self.turn}


@dataclass(frozen=True, slots=True)
class ToolCallStarted:
    type: ClassVar[str] = "tool_call"
    call: ToolCall
    turn: int

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "turn": self.turn, "tool_call": _call_dict(self.call)}


@dataclass(frozen=True, slots=True)
class ToolCallCompleted:
    type: ClassVar[str] = "tool_result"
    call: ToolCall
    result: ToolResult
    output: str
    duration_ms: float
    turn: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "turn": self.turn,
            "tool_call": _call_dict(self.call),
            "success": self.result.success,
            "output": self.output,
            "error": self.result.error,
            "duration_ms": round(self.duration_ms, 1),
        }


@dataclass(frozen=True, slots=True)
class TurnCompleted:
    type: ClassVar[str] = "turn_completed"
    turn: int
    usage: TokenUsage
    finish_reason: str | None
    tool_calls: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "turn": self.turn,
            "usage": _usage_dict(self.usage),
            "finish_reason": self.finish_reason,
            "tool_calls": self.tool_calls,
        }


@dataclass(frozen=True, slots=True)
class RunCompleted:
    type: ClassVar[str] = "run_completed"
    run_id: str
    agent: str
    output: str
    new_messages: tuple[Message, ...]
    usage: TokenUsage
    turns: int
    finish_reason: str
    duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "run_id": self.run_id,
            "agent": self.agent,
            "output": self.output,
            "usage": _usage_dict(self.usage),
            "turns": self.turns,
            "finish_reason": self.finish_reason,
            "duration_ms": round(self.duration_ms, 1),
        }


@dataclass(frozen=True, slots=True)
class RunFailed:
    type: ClassVar[str] = "run_failed"
    run_id: str
    agent: str
    error: str
    error_type: str
    new_messages: tuple[Message, ...]
    usage: TokenUsage
    turns: int
    duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "run_id": self.run_id,
            "agent": self.agent,
            "error": self.error,
            "error_type": self.error_type,
            "usage": _usage_dict(self.usage),
            "turns": self.turns,
            "duration_ms": round(self.duration_ms, 1),
        }


AgentEvent = (
    RunStarted
    | TextDelta
    | ToolCallStarted
    | ToolCallCompleted
    | TurnCompleted
    | RunCompleted
    | RunFailed
)


class AgentRunError(RuntimeError):
    """Raised by :meth:`AgentRunner.run` when the run fails."""

    def __init__(self, failure: RunFailed) -> None:
        super().__init__(f"{failure.error_type}: {failure.error}")
        self.failure = failure


# ---------------------------------------------------------------------------
# Hooks + policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ToolDecision:
    """Verdict returned by :meth:`RunHooks.before_tool_call`."""

    allow: bool
    reason: str = ""

    @classmethod
    def deny(cls, reason: str) -> ToolDecision:
        return cls(allow=False, reason=reason)


class RunHooks:
    """Lifecycle callbacks around an agent run. Override what you need.

    Observer hooks (``on_*`` / ``after_tool_call`` returning ``None``)
    must not raise — exceptions are logged and swallowed so telemetry
    can never break a user-facing run. ``before_tool_call`` is a
    *policy* hook and fails closed: if it raises, the call is denied.
    """

    async def on_run_start(self, ctx: RunContext, agent: Agent) -> None:
        return None

    async def on_llm_start(
        self, ctx: RunContext, agent: Agent, messages: Sequence[Message]
    ) -> None:
        return None

    async def on_llm_end(
        self, ctx: RunContext, agent: Agent, message: Message, usage: TokenUsage
    ) -> None:
        return None

    async def before_tool_call(
        self, ctx: RunContext, agent: Agent, call: ToolCall
    ) -> ToolDecision | None:
        return None

    async def after_tool_call(
        self, ctx: RunContext, agent: Agent, call: ToolCall, result: ToolResult
    ) -> ToolResult | None:
        return None

    async def on_run_end(
        self, ctx: RunContext, agent: Agent, outcome: RunCompleted | RunFailed
    ) -> None:
        return None


class CompositeHooks(RunHooks):
    """Fan out to several hooks in order."""

    def __init__(self, hooks: Iterable[RunHooks]) -> None:
        self._hooks = [h for h in hooks if h is not None]

    async def _observe(self, method: str, *args: Any) -> None:
        for hook in self._hooks:
            try:
                await getattr(hook, method)(*args)
            except Exception:
                logger.exception("RunHooks.%s failed in %s", method, type(hook).__name__)

    async def on_run_start(self, ctx: RunContext, agent: Agent) -> None:
        await self._observe("on_run_start", ctx, agent)

    async def on_llm_start(
        self, ctx: RunContext, agent: Agent, messages: Sequence[Message]
    ) -> None:
        await self._observe("on_llm_start", ctx, agent, messages)

    async def on_llm_end(
        self, ctx: RunContext, agent: Agent, message: Message, usage: TokenUsage
    ) -> None:
        await self._observe("on_llm_end", ctx, agent, message, usage)

    async def before_tool_call(
        self, ctx: RunContext, agent: Agent, call: ToolCall
    ) -> ToolDecision | None:
        for hook in self._hooks:
            try:
                decision = await hook.before_tool_call(ctx, agent, call)
            except Exception as exc:
                logger.exception("Policy hook %s failed — denying call", type(hook).__name__)
                return ToolDecision.deny(f"policy check failed: {type(exc).__name__}")
            if decision is not None and not decision.allow:
                return decision
        return None

    async def after_tool_call(
        self, ctx: RunContext, agent: Agent, call: ToolCall, result: ToolResult
    ) -> ToolResult | None:
        current = result
        for hook in self._hooks:
            try:
                replaced = await hook.after_tool_call(ctx, agent, call, current)
            except Exception:
                logger.exception("RunHooks.after_tool_call failed in %s", type(hook).__name__)
                continue
            if replaced is not None:
                current = replaced
        return current if current is not result else None

    async def on_run_end(
        self, ctx: RunContext, agent: Agent, outcome: RunCompleted | RunFailed
    ) -> None:
        await self._observe("on_run_end", ctx, agent, outcome)


class ToolPolicy(RunHooks):
    """Allow/deny-list + per-run budget for tool calls (harness dim. #7).

    - ``allow``: if given, only these tool names may run.
    - ``deny``: these tool names never run (wins over ``allow``).
    - ``max_calls``: hard cap on tool invocations per run — a cheap guard
      against runaway loops burning money on external APIs.
    """

    def __init__(
        self,
        *,
        allow: Iterable[str] | None = None,
        deny: Iterable[str] = (),
        max_calls: int | None = None,
    ) -> None:
        self._allow = set(allow) if allow is not None else None
        self._deny = set(deny)
        self._max_calls = max_calls

    async def before_tool_call(
        self, ctx: RunContext, agent: Agent, call: ToolCall
    ) -> ToolDecision | None:
        if call.name in self._deny:
            return ToolDecision.deny(f"tool {call.name!r} is disabled by policy")
        if self._allow is not None and call.name not in self._allow:
            return ToolDecision.deny(f"tool {call.name!r} is not permitted for this agent")
        if self._max_calls is not None:
            used = int(ctx.state.get("_policy_tool_calls", 0))
            if used >= self._max_calls:
                return ToolDecision.deny(
                    f"tool-call budget exhausted ({self._max_calls} per run); "
                    "answer with the information you already have"
                )
            ctx.state["_policy_tool_calls"] = used + 1
        return None


# ---------------------------------------------------------------------------
# Context window management (harness dimension #4)
# ---------------------------------------------------------------------------


Summarize = Callable[[Sequence[Message]], Awaitable[str]]


class ContextWindow:
    """Fit a transcript into the model's context window.

    Trimming happens at *exchange* granularity — an exchange is a user
    message plus everything up to the next user message (assistant
    replies, tool calls and tool results). Whole exchanges are dropped
    oldest-first, which guarantees:

    - leading ``system`` messages are always kept;
    - the most recent exchange (the run in progress) is always kept;
    - the kept window starts with a ``user`` message (Anthropic requires
      this) and never orphans a ``tool`` result from its ``tool_calls``.

    When anything is dropped, an optional async ``summarize`` callback
    condenses the dropped exchanges; otherwise a short system note tells
    the model that earlier turns were elided.
    """

    def __init__(
        self,
        *,
        max_tokens: int | None = None,
        reserve_tokens: int = 4_096,
        max_messages: int | None = None,
        token_counter: Callable[[Message], int] | None = None,
        summarize: Summarize | None = None,
    ) -> None:
        if reserve_tokens < 0:
            raise ValueError("reserve_tokens must be >= 0")
        self._max_tokens = max_tokens
        self._reserve = reserve_tokens
        self._max_messages = max_messages
        self._count = token_counter or estimate_message_tokens
        self._summarize = summarize

    @staticmethod
    def exchanges(messages: Sequence[Message]) -> list[list[Message]]:
        groups: list[list[Message]] = []
        for msg in messages:
            if msg.role == "user" or not groups:
                groups.append([msg])
            else:
                groups[-1].append(msg)
        return groups

    def budget(self, model_window: int) -> int:
        window = model_window if model_window > 0 else 8_192
        if self._max_tokens is not None:
            window = min(window, self._max_tokens)
        # Never let the reserve swallow the whole window on small models.
        return max(window - self._reserve, window // 2)

    async def fit(self, messages: Sequence[Message], model_window: int) -> list[Message]:
        system = [m for m in messages if m.role == "system"]
        convo = [m for m in messages if m.role != "system"]
        if not convo:
            return list(messages)

        budget = self.budget(model_window) - sum(self._count(m) for m in system)
        groups = self.exchanges(convo)
        kept: list[list[Message]] = [groups[-1]]
        used = sum(self._count(m) for m in groups[-1])
        count = len(groups[-1])
        for group in reversed(groups[:-1]):
            cost = sum(self._count(m) for m in group)
            if used + cost > budget:
                break
            if self._max_messages is not None and count + len(group) > self._max_messages:
                break
            kept.append(group)
            used += cost
            count += len(group)
        kept.reverse()

        # Ensure the window opens on a user turn.
        while len(kept) > 1 and kept[0][0].role != "user":
            kept.pop(0)

        dropped_groups = groups[: len(groups) - len(kept)]
        out = list(system)
        if dropped_groups:
            dropped = [m for g in dropped_groups for m in g]
            note = await self._summary_note(dropped)
            out.append(Message(role="system", content=note, metadata={"compaction": True}))
        out.extend(m for g in kept for m in g)
        return out

    async def _summary_note(self, dropped: Sequence[Message]) -> str:
        if self._summarize is not None:
            try:
                summary = (await self._summarize(dropped)).strip()
                if summary:
                    return f"Summary of earlier conversation:\n{summary}"
            except Exception:
                logger.exception("Context summarizer failed; falling back to elision note")
        return (
            f"[{len(dropped)} earlier messages were omitted to fit the context window. "
            "Ask the user if you need details from earlier in the conversation.]"
        )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

AgentInput = str | Message | Sequence[Message]


@contextlib.asynccontextmanager
async def _closing(stream: Any) -> AsyncIterator[Any]:
    """Deterministically close an async generator (cancels its cleanup
    path promptly when the consumer stops early)."""
    try:
        yield stream
    finally:
        aclose = getattr(stream, "aclose", None)
        if aclose is not None:
            await aclose()


def _normalize_input(value: AgentInput) -> list[Message]:
    if isinstance(value, str):
        return [Message(role="user", content=value)]
    if isinstance(value, Message):
        return [value]
    return list(value)


class AgentRunner:
    """Execute :class:`Agent` definitions against a model provider.

    Args:
        provider: Any :class:`LLMProviderProtocol` (including
            ``FallbackProvider`` chains).
        hooks: Lifecycle hooks / policies (a list is wrapped in
            :class:`CompositeHooks`).
        context_window: Trimming policy; defaults to :class:`ContextWindow`
            with a 4k-token response reserve.
    """

    def __init__(
        self,
        provider: LLMProviderProtocol,
        *,
        hooks: RunHooks | Sequence[RunHooks] | None = None,
        context_window: ContextWindow | None = None,
    ) -> None:
        self.provider = provider
        if hooks is None:
            self._hooks: RunHooks = RunHooks()
        elif isinstance(hooks, RunHooks):
            self._hooks = hooks
        else:
            self._hooks = CompositeHooks(hooks)
        self._window = context_window or ContextWindow()

    # -- public API -----------------------------------------------------

    async def run(
        self,
        agent: Agent,
        input: AgentInput,
        *,
        history: Sequence[Message] = (),
        context: RunContext | None = None,
        system_prompt: str | None = None,
    ) -> AgentResponse:
        """Run to completion and return the final answer.

        Raises :class:`AgentRunError` if the run fails.
        """
        outcome: RunCompleted | RunFailed | None = None
        tool_calls: list[dict[str, Any]] = []
        async for event in self.run_stream(
            agent, input, history=history, context=context, system_prompt=system_prompt
        ):
            if isinstance(event, ToolCallCompleted):
                tool_calls.append({"name": event.call.name, "success": event.result.success})
            if isinstance(event, (RunCompleted, RunFailed)):
                outcome = event
        assert outcome is not None
        if isinstance(outcome, RunFailed):
            raise AgentRunError(outcome)
        return AgentResponse(
            output=outcome.output,
            messages=list(outcome.new_messages),
            usage=outcome.usage,
            metadata={
                "run_id": outcome.run_id,
                "agent": outcome.agent,
                "turns": outcome.turns,
                "finish_reason": outcome.finish_reason,
                "tool_calls": tool_calls,
                "duration_ms": outcome.duration_ms,
            },
        )

    async def run_stream(
        self,
        agent: Agent,
        input: AgentInput,
        *,
        history: Sequence[Message] = (),
        context: RunContext | None = None,
        system_prompt: str | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Run the loop, yielding :data:`AgentEvent` values as they happen.

        Always terminates with exactly one :class:`RunCompleted` or
        :class:`RunFailed` event (unless the consumer stops iterating).

        Args:
            agent: The agent definition.
            input: The new user turn (text, a message, or messages).
            history: Prior conversation (system messages are ignored —
                the agent's instructions / ``system_prompt`` are
                authoritative).
            context: Run context; created if omitted.
            system_prompt: Overrides ``agent.instructions`` (used by the
                application layer to inject identity / soul / skills).
        """
        run_id = context.run_id if context else f"run_{uuid.uuid4().hex[:16]}"
        ctx = context or RunContext(run_id=run_id, agent_name=agent.name)
        toolset = Toolset(agent.tools)
        tool_list = list(toolset) or None
        started = time.perf_counter()

        system_text = agent.instructions if system_prompt is None else system_prompt
        base: list[Message] = [Message(role="system", content=system_text)] if system_text else []
        prior = [m for m in history if m.role != "system"]
        new_messages: list[Message] = _normalize_input(input)
        usage_total = TokenUsage()
        turn = 0

        span = get_tracer().start_span(
            "agent.run",
            attributes={
                "agentcook.agent.name": agent.name,
                "agentcook.run.id": run_id,
                "agentcook.tools.count": len(toolset),
                "agentcook.history.count": len(prior),
                "agentcook.run.depth": ctx.depth,
            },
        )
        span.__enter__()
        try:
            yield RunStarted(run_id=run_id, agent=agent.name)
            await self._hooks.on_run_start(ctx, agent)

            for turn in range(1, agent.max_turns + 1):
                prompt = await self._window.fit(
                    [*base, *prior, *new_messages], self.provider.context_window
                )
                await self._hooks.on_llm_start(ctx, agent, prompt)

                text_parts: list[str] = []
                calls: dict[str, ToolCall] = {}
                finish: str | None = None
                usage: TokenUsage | None = None
                stream = self.provider.stream_chat(
                    prompt,
                    tools=tool_list,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                )
                async with _closing(stream):
                    async for chunk in stream:
                        if chunk.delta_content:
                            text_parts.append(chunk.delta_content)
                            yield TextDelta(text=chunk.delta_content, turn=turn)
                        for call in chunk.delta_tool_calls:
                            call_id = call.id or f"call_{uuid.uuid4().hex[:12]}"
                            calls[call_id] = ToolCall(
                                id=call_id, name=call.name, arguments=dict(call.arguments or {})
                            )
                        if chunk.usage is not None:
                            usage = chunk.usage
                        if chunk.finish_reason:
                            finish = chunk.finish_reason

                text = "".join(text_parts)
                if usage is None:
                    usage = TokenUsage(
                        input=sum(estimate_message_tokens(m) for m in prompt),
                        output=estimate_tokens(text),
                    )
                usage_total = TokenUsage(
                    input=usage_total.input + usage.input,
                    output=usage_total.output + usage.output,
                    cached=usage_total.cached + usage.cached,
                )
                assistant = Message(
                    role="assistant",
                    content=text,
                    tool_calls=tuple(calls.values()) or None,
                )
                new_messages.append(assistant)
                await self._hooks.on_llm_end(ctx, agent, assistant, usage)
                yield TurnCompleted(
                    turn=turn, usage=usage, finish_reason=finish, tool_calls=len(calls)
                )

                if not calls:
                    outcome = RunCompleted(
                        run_id=run_id,
                        agent=agent.name,
                        output=text,
                        new_messages=tuple(new_messages),
                        usage=usage_total,
                        turns=turn,
                        finish_reason=finish or "stop",
                        duration_ms=(time.perf_counter() - started) * 1000,
                    )
                    span.set_attribute("agentcook.run.turns", turn)
                    span.set_attribute("agentcook.run.finish_reason", outcome.finish_reason)
                    await self._hooks.on_run_end(ctx, agent, outcome)
                    yield outcome
                    return

                ordered = list(calls.values())
                for call in ordered:
                    yield ToolCallStarted(call=call, turn=turn)
                results: dict[str, str] = {}
                executions = self._execute_tools(agent, toolset, ordered, ctx, turn)
                async with _closing(executions):
                    async for completed in executions:
                        results[completed.call.id] = completed.output
                        yield completed
                for call in ordered:
                    new_messages.append(
                        Message(
                            role="tool",
                            content=results[call.id],
                            name=call.name,
                            tool_call_id=call.id,
                        )
                    )

            # Turn budget exhausted while the model still wanted tools.
            final_text = next(
                (m.content for m in reversed(new_messages) if m.role == "assistant" and m.content),
                "",
            )
            outcome = RunCompleted(
                run_id=run_id,
                agent=agent.name,
                output=final_text,
                new_messages=tuple(new_messages),
                usage=usage_total,
                turns=turn,
                finish_reason="max_turns",
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            span.set_attribute("agentcook.run.turns", turn)
            span.set_attribute("agentcook.run.finish_reason", "max_turns")
            await self._hooks.on_run_end(ctx, agent, outcome)
            yield outcome
        except Exception as exc:
            logger.warning("Agent run %s failed: %s", run_id, exc, exc_info=True)
            span.record_exception(exc)
            failure = RunFailed(
                run_id=run_id,
                agent=agent.name,
                error=str(exc)[:500] or type(exc).__name__,
                error_type=type(exc).__name__,
                new_messages=tuple(new_messages),
                usage=usage_total,
                turns=turn,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            await self._hooks.on_run_end(ctx, agent, failure)
            yield failure
        finally:
            span.__exit__(None, None, None)

    # -- tool execution -------------------------------------------------

    async def _execute_tools(
        self,
        agent: Agent,
        toolset: Toolset,
        calls: Sequence[ToolCall],
        ctx: RunContext,
        turn: int,
    ) -> AsyncIterator[ToolCallCompleted]:
        if not agent.parallel_tool_calls:
            for call in calls:
                yield await self._execute_one(agent, toolset, call, ctx, turn)
            return

        tasks = [
            asyncio.create_task(self._execute_one(agent, toolset, call, ctx, turn))
            for call in calls
        ]
        try:
            for next_done in asyncio.as_completed(tasks):
                yield await next_done
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()

    async def _execute_one(
        self,
        agent: Agent,
        toolset: Toolset,
        call: ToolCall,
        ctx: RunContext,
        turn: int,
    ) -> ToolCallCompleted:
        started = time.perf_counter()
        token = _set_run_context(ctx)
        with get_tracer().start_span(
            "tool.invoke",
            attributes={
                "agentcook.tool.name": call.name,
                "agentcook.tool.call_id": call.id,
                "agentcook.agent.name": agent.name,
            },
        ) as span:
            try:
                result = await self._invoke(agent, toolset, call, ctx)
                replaced = await self._hooks.after_tool_call(ctx, agent, call, result)
                if replaced is not None:
                    result = replaced
            finally:
                _reset_run_context(token)
            span.set_attribute("agentcook.tool.success", result.success)
        output = render_tool_output(result, max_chars=agent.max_tool_output_chars)
        return ToolCallCompleted(
            call=call,
            result=result,
            output=output,
            duration_ms=(time.perf_counter() - started) * 1000,
            turn=turn,
        )

    async def _invoke(
        self, agent: Agent, toolset: Toolset, call: ToolCall, ctx: RunContext
    ) -> ToolResult:
        tool_obj = toolset.get(call.name)
        if tool_obj is None:
            available = ", ".join(toolset.names) or "(none)"
            return ToolResult(
                success=False,
                error=f"unknown tool {call.name!r}; available tools: {available}",
                metadata={"kind": "unknown_tool"},
            )
        decision = await self._hooks.before_tool_call(ctx, agent, call)
        if decision is not None and not decision.allow:
            return ToolResult(
                success=False,
                error=f"tool call denied: {decision.reason}",
                metadata={"kind": "denied"},
            )
        timeout = getattr(tool_obj, "timeout", None) or agent.tool_timeout
        try:
            result = await asyncio.wait_for(tool_obj.invoke(dict(call.arguments)), timeout)
        except TimeoutError:
            return ToolResult(
                success=False,
                error=f"tool {call.name!r} timed out after {timeout:g}s",
                metadata={"kind": "timeout"},
            )
        except Exception as exc:  # ToolProtocol says don't raise; enforce it.
            logger.warning("Tool %s raised: %s", call.name, exc, exc_info=True)
            return ToolResult(
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                metadata={"kind": "exception"},
            )
        if not isinstance(result, ToolResult):
            return ToolResult(success=True, output=result)
        return result


# ---------------------------------------------------------------------------
# Sub-agents as tools (harness dimension #5)
# ---------------------------------------------------------------------------


class AgentTool:
    """Expose an :class:`Agent` as a tool another agent can delegate to.

    The "agents as tools" pattern keeps orchestration inside the same
    loop: the parent model decides *when* to delegate, the sub-agent
    runs its own loop with its own instructions and tools, and only the
    final answer flows back. Nesting is bounded by ``max_depth``.

    Each delegation is recorded under ``ctx.state["delegations"]`` of the
    parent run so the application can render a delegation graph.
    """

    def __init__(
        self,
        agent: Agent,
        runner: AgentRunner,
        *,
        name: str | None = None,
        description: str | None = None,
        max_depth: int = 3,
    ) -> None:
        self._agent = agent
        self._runner = runner
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in agent.name)
        self._name = name or f"delegate_to_{safe}"[:64]
        self._description = description or (
            f"Delegate a self-contained task to the '{agent.name}' agent and get its answer."
            + (f" {agent.description}" if agent.description else "")
        )
        self._max_depth = max_depth

    @property
    def agent(self) -> Agent:
        return self._agent

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": (
                        "Complete, self-contained instructions for the sub-agent, "
                        "including any context it needs."
                    ),
                }
            },
            "required": ["task"],
            "additionalProperties": False,
        }

    async def invoke(self, arguments: dict[str, Any]) -> ToolResult:
        task = str(arguments.get("task", "")).strip()
        if not task:
            return ToolResult(success=False, error="argument 'task' must be a non-empty string")
        parent = current_run_context()
        depth = (parent.depth if parent else 0) + 1
        if depth > self._max_depth:
            return ToolResult(
                success=False,
                error=f"delegation depth limit reached ({self._max_depth})",
            )
        child = RunContext(
            run_id=f"run_{uuid.uuid4().hex[:16]}",
            agent_name=self._agent.name,
            session_id=parent.session_id if parent else None,
            user_id=parent.user_id if parent else None,
            depth=depth,
            metadata={"parent_run_id": parent.run_id if parent else None},
        )
        started = time.perf_counter()
        try:
            response = await self._runner.run(self._agent, task, context=child)
        except AgentRunError as exc:
            outcome = {"error": str(exc)}
            success = False
            result = ToolResult(success=False, error=f"sub-agent failed: {exc}")
        else:
            outcome = {"turns": response.metadata.get("turns")}
            success = True
            result = ToolResult(
                success=True,
                output=response.output,
                metadata={
                    "agent": self._agent.name,
                    "run_id": child.run_id,
                    "turns": response.metadata.get("turns"),
                    "usage": {
                        "input_tokens": response.usage.input,
                        "output_tokens": response.usage.output,
                    },
                },
            )
        if parent is not None:
            parent.state.setdefault("delegations", []).append(
                {
                    "from": parent.agent_name,
                    "to": self._agent.name,
                    "run_id": child.run_id,
                    "success": success,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    **outcome,
                }
            )
        return result


__all__ = [
    "Agent",
    "AgentEvent",
    "AgentRunError",
    "AgentRunner",
    "AgentTool",
    "CompositeHooks",
    "ContextWindow",
    "RunCompleted",
    "RunContext",
    "RunFailed",
    "RunHooks",
    "RunStarted",
    "TextDelta",
    "ToolCallCompleted",
    "ToolCallStarted",
    "ToolDecision",
    "ToolPolicy",
    "TurnCompleted",
]
