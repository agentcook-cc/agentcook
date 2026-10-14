"""Tests for the agent loop (agentcook_core.agent)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Sequence
from typing import Any

import pytest

from agentcook_core import (
    Agent,
    AgentRunError,
    AgentRunner,
    AgentTool,
    ChatChunk,
    ChatResponse,
    ContextWindow,
    LLMProviderProtocol,
    Message,
    RunCompleted,
    RunContext,
    RunFailed,
    RunHooks,
    RunStarted,
    TextDelta,
    TokenUsage,
    ToolCall,
    ToolCallCompleted,
    ToolCallStarted,
    ToolDecision,
    ToolPolicy,
    ToolProtocol,
    ToolResult,
    TurnCompleted,
    tool,
)

pytestmark = pytest.mark.unit

Step = Callable[[Sequence[Message]], list[ChatChunk]]


class ScriptedProvider:
    """Plays back one scripted response per LLM call and records prompts."""

    def __init__(self, steps: Sequence[Step | list[ChatChunk]], *, window: int = 100_000) -> None:
        self._steps = list(steps)
        self.prompts: list[list[Message]] = []
        self.tools_seen: list[list[str]] = []
        self._window = window

    @property
    def model_name(self) -> str:
        return "scripted"

    @property
    def context_window(self) -> int:
        return self._window

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    async def chat(self, messages: Sequence[Message], **_: Any) -> ChatResponse:  # pragma: no cover
        raise NotImplementedError

    async def stream_chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolProtocol] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        self.prompts.append(list(messages))
        self.tools_seen.append([t.name for t in tools or ()])
        step = self._steps.pop(0)
        chunks = step(messages) if callable(step) else step
        for chunk in chunks:
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk


def text(*parts: str, usage: TokenUsage | None = None) -> list[ChatChunk]:
    chunks = [ChatChunk(delta_content=p) for p in parts]
    chunks.append(ChatChunk(finish_reason="stop", usage=usage))
    return chunks


def calls(*tool_calls: ToolCall) -> list[ChatChunk]:
    return [ChatChunk(delta_tool_calls=tuple(tool_calls), finish_reason="tool_calls")]


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


async def collect(stream: AsyncIterator[Any]) -> list[Any]:
    return [event async for event in stream]


def test_provider_fixture_satisfies_protocol() -> None:
    assert isinstance(ScriptedProvider([]), LLMProviderProtocol)


def test_agent_validation() -> None:
    with pytest.raises(ValueError):
        Agent(name="")
    with pytest.raises(ValueError):
        Agent(name="a", max_turns=0)
    with pytest.raises(ValueError):
        Agent(name="a", tools=(add, add))
    agent = Agent(name="a", tools=[add])  # type: ignore[arg-type]
    assert agent.tools == (add,)
    assert agent.with_tools(add).tools == (add,)


async def test_plain_answer_streams_text_and_completes() -> None:
    provider = ScriptedProvider([text("Hel", "lo", usage=TokenUsage(input=10, output=2))])
    runner = AgentRunner(provider)
    events = await collect(runner.run_stream(Agent(name="a", instructions="Be nice."), "hi"))

    assert isinstance(events[0], RunStarted)
    assert [e.text for e in events if isinstance(e, TextDelta)] == ["Hel", "lo"]
    done = events[-1]
    assert isinstance(done, RunCompleted)
    assert done.output == "Hello"
    assert done.turns == 1
    assert done.finish_reason == "stop"
    assert done.usage == TokenUsage(input=10, output=2)
    assert [m.role for m in done.new_messages] == ["user", "assistant"]
    # system prompt goes first
    assert provider.prompts[0][0] == Message(role="system", content="Be nice.")


async def test_tool_loop_executes_tools_and_feeds_results_back() -> None:
    provider = ScriptedProvider(
        [
            calls(ToolCall(id="c1", name="add", arguments={"a": 2, "b": 3})),
            text("The answer is 5."),
        ]
    )
    runner = AgentRunner(provider)
    events = await collect(runner.run_stream(Agent(name="a", tools=(add,)), "2+3?"))

    started = [e for e in events if isinstance(e, ToolCallStarted)]
    completed = [e for e in events if isinstance(e, ToolCallCompleted)]
    assert [e.call.name for e in started] == ["add"]
    assert completed[0].output == "5" and completed[0].result.success
    assert len([e for e in events if isinstance(e, TurnCompleted)]) == 2

    second_prompt = provider.prompts[1]
    assert second_prompt[-2].role == "assistant" and second_prompt[-2].tool_calls
    tool_msg = second_prompt[-1]
    assert tool_msg.role == "tool" and tool_msg.tool_call_id == "c1" and tool_msg.content == "5"
    assert provider.tools_seen[0] == ["add"]

    done = events[-1]
    assert isinstance(done, RunCompleted) and done.output == "The answer is 5."
    assert [m.role for m in done.new_messages] == ["user", "assistant", "tool", "assistant"]


async def test_parallel_tool_calls_keep_call_order_in_transcript() -> None:
    @tool
    async def slow(x: str) -> str:
        await asyncio.sleep(0.05)
        return f"slow-{x}"

    @tool
    async def fast(x: str) -> str:
        return f"fast-{x}"

    provider = ScriptedProvider(
        [
            calls(
                ToolCall(id="1", name="slow", arguments={"x": "a"}),
                ToolCall(id="2", name="fast", arguments={"x": "b"}),
            ),
            text("ok"),
        ]
    )
    events = await collect(
        AgentRunner(provider).run_stream(Agent(name="a", tools=(slow, fast)), "go")
    )
    completed = [e.call.id for e in events if isinstance(e, ToolCallCompleted)]
    assert completed == ["2", "1"]  # fast finishes first
    tool_msgs = [m for m in provider.prompts[1] if m.role == "tool"]
    assert [m.tool_call_id for m in tool_msgs] == ["1", "2"]  # transcript keeps call order


async def test_unknown_tool_invalid_args_and_timeouts_become_error_results() -> None:
    @tool
    async def sleepy() -> str:
        await asyncio.sleep(5)
        return "never"

    provider = ScriptedProvider(
        [
            calls(
                ToolCall(id="1", name="nope", arguments={}),
                ToolCall(id="2", name="add", arguments={"a": "x", "b": 1}),
                ToolCall(id="3", name="sleepy", arguments={}),
            ),
            text("recovered"),
        ]
    )
    agent = Agent(name="a", tools=(add, sleepy), tool_timeout=0.05)
    events = await collect(AgentRunner(provider).run_stream(agent, "go"))
    outputs = {e.call.id: e.output for e in events if isinstance(e, ToolCallCompleted)}
    assert outputs["1"].startswith("ERROR: unknown tool 'nope'")
    assert "available tools: add, sleepy" in outputs["1"]
    assert outputs["2"].startswith("ERROR: argument 'a' must be of type integer")
    assert outputs["3"] == "ERROR: tool 'sleepy' timed out after 0.05s"
    assert isinstance(events[-1], RunCompleted) and events[-1].output == "recovered"


async def test_misbehaving_tool_that_raises_is_contained() -> None:
    class RaisingTool:
        name = "raiser"
        description = "raises"
        parameters_schema: dict[str, Any] = {"type": "object", "properties": {}}

        async def invoke(self, arguments: dict[str, Any]) -> ToolResult:
            raise ValueError("bad tool")

    provider = ScriptedProvider([calls(ToolCall(id="1", name="raiser")), text("fine")])
    events = await collect(
        AgentRunner(provider).run_stream(Agent(name="a", tools=(RaisingTool(),)), "go")
    )
    result = next(e for e in events if isinstance(e, ToolCallCompleted))
    assert result.output == "ERROR: ValueError: bad tool"


async def test_max_turns_stops_runaway_loops() -> None:
    loop_step = calls(ToolCall(id="x", name="add", arguments={"a": 1, "b": 1}))
    provider = ScriptedProvider([loop_step, loop_step, loop_step])
    events = await collect(
        AgentRunner(provider).run_stream(Agent(name="a", tools=(add,), max_turns=3), "go")
    )
    done = events[-1]
    assert isinstance(done, RunCompleted)
    assert done.finish_reason == "max_turns" and done.turns == 3


async def test_provider_error_yields_run_failed_and_run_raises() -> None:
    provider = ScriptedProvider([[ChatChunk(delta_content="par"), RuntimeError("upstream 500")]])
    events = await collect(AgentRunner(provider).run_stream(Agent(name="a"), "go"))
    failed = events[-1]
    assert isinstance(failed, RunFailed)
    assert failed.error_type == "RuntimeError" and "upstream 500" in failed.error

    provider2 = ScriptedProvider([[RuntimeError("boom")]])
    with pytest.raises(AgentRunError, match="boom"):
        await AgentRunner(provider2).run(Agent(name="a"), "go")


async def test_run_returns_agent_response() -> None:
    provider = ScriptedProvider(
        [calls(ToolCall(id="1", name="add", arguments={"a": 1, "b": 2})), text("3")]
    )
    response = await AgentRunner(provider).run(Agent(name="calc", tools=(add,)), "1+2")
    assert response.output == "3"
    assert response.metadata["turns"] == 2
    assert response.metadata["tool_calls"] == [{"name": "add", "success": True}]


async def test_history_is_included_and_its_system_messages_ignored() -> None:
    provider = ScriptedProvider([text("ok")])
    history = [
        Message(role="system", content="stale system"),
        Message(role="user", content="earlier q"),
        Message(role="assistant", content="earlier a"),
    ]
    await AgentRunner(provider).run(
        Agent(name="a", instructions="fresh"), "now", history=history
    )
    prompt = provider.prompts[0]
    assert [m.content for m in prompt] == ["fresh", "earlier q", "earlier a", "now"]


async def test_system_prompt_override() -> None:
    provider = ScriptedProvider([text("ok")])
    await AgentRunner(provider).run(
        Agent(name="a", instructions="default"), "hi", system_prompt="override"
    )
    assert provider.prompts[0][0].content == "override"


async def test_hooks_lifecycle_and_policy_denial() -> None:
    log: list[str] = []

    class Recorder(RunHooks):
        async def on_run_start(self, ctx: RunContext, agent: Agent) -> None:
            log.append("run_start")

        async def on_llm_start(self, ctx: RunContext, agent: Agent, messages: Any) -> None:
            log.append("llm_start")

        async def on_llm_end(self, ctx: RunContext, agent: Agent, message: Any, usage: Any) -> None:
            log.append("llm_end")

        async def after_tool_call(
            self, ctx: RunContext, agent: Agent, call: ToolCall, result: ToolResult
        ) -> ToolResult | None:
            log.append(f"after:{call.name}:{result.success}")
            return None

        async def on_run_end(self, ctx: RunContext, agent: Agent, outcome: Any) -> None:
            log.append(f"run_end:{outcome.type}")

    provider = ScriptedProvider(
        [calls(ToolCall(id="1", name="add", arguments={"a": 1, "b": 1})), text("done")]
    )
    runner = AgentRunner(provider, hooks=[Recorder(), ToolPolicy(deny=["add"])])
    events = await collect(runner.run_stream(Agent(name="a", tools=(add,)), "go"))
    result = next(e for e in events if isinstance(e, ToolCallCompleted))
    assert result.output == "ERROR: tool call denied: tool 'add' is disabled by policy"
    assert log == [
        "run_start",
        "llm_start",
        "llm_end",
        "after:add:False",
        "llm_start",
        "llm_end",
        "run_end:run_completed",
    ]


async def test_policy_hook_that_raises_fails_closed() -> None:
    class Broken(RunHooks):
        async def before_tool_call(self, ctx: Any, agent: Any, call: Any) -> ToolDecision | None:
            raise RuntimeError("policy db down")

    provider = ScriptedProvider(
        [calls(ToolCall(id="1", name="add", arguments={"a": 1, "b": 1})), text("x")]
    )
    events = await collect(
        AgentRunner(provider, hooks=[Broken()]).run_stream(Agent(name="a", tools=(add,)), "go")
    )
    result = next(e for e in events if isinstance(e, ToolCallCompleted))
    assert "policy check failed" in result.output


async def test_tool_policy_allow_list_and_budget() -> None:
    policy = ToolPolicy(allow=["add"], max_calls=1)
    ctx = RunContext(run_id="r", agent_name="a")
    agent = Agent(name="a")
    assert await policy.before_tool_call(ctx, agent, ToolCall(id="1", name="add")) is None
    budget = await policy.before_tool_call(ctx, agent, ToolCall(id="2", name="add"))
    assert budget is not None and not budget.allow and "budget" in budget.reason
    other = await policy.before_tool_call(ctx, agent, ToolCall(id="3", name="rm"))
    assert other is not None and "not permitted" in other.reason


async def test_observer_hook_failure_does_not_break_run() -> None:
    class Noisy(RunHooks):
        async def on_llm_end(self, *args: Any) -> None:
            raise RuntimeError("metrics backend down")

    provider = ScriptedProvider([text("still fine")])
    response = await AgentRunner(provider, hooks=[Noisy()]).run(Agent(name="a"), "go")
    assert response.output == "still fine"


async def test_run_context_reaches_tools() -> None:
    @tool
    def whoami(ctx: RunContext) -> str:
        ctx.state["touched"] = True
        return f"{ctx.user_id}/{ctx.session_id}"

    provider = ScriptedProvider([calls(ToolCall(id="1", name="whoami")), text("ok")])
    ctx = RunContext(run_id="r1", agent_name="a", user_id="u1", session_id="s1")
    events = await collect(
        AgentRunner(provider).run_stream(Agent(name="a", tools=(whoami,)), "go", context=ctx)
    )
    result = next(e for e in events if isinstance(e, ToolCallCompleted))
    assert result.output == "u1/s1"
    assert ctx.state["touched"] is True


async def test_missing_tool_call_ids_are_generated() -> None:
    provider = ScriptedProvider(
        [calls(ToolCall(id="", name="add", arguments={"a": 1, "b": 2})), text("3")]
    )
    events = await collect(AgentRunner(provider).run_stream(Agent(name="a", tools=(add,)), "q"))
    call_id = next(e for e in events if isinstance(e, ToolCallStarted)).call.id
    assert call_id.startswith("call_")
    tool_msg = next(m for m in provider.prompts[1] if m.role == "tool")
    assert tool_msg.tool_call_id == call_id


async def test_usage_is_estimated_when_provider_reports_none() -> None:
    provider = ScriptedProvider([text("你好世界")])
    response = await AgentRunner(provider).run(Agent(name="a"), "你好")
    assert response.usage.output == 4  # one token per CJK char
    assert response.usage.input > 0


async def test_consumer_stopping_early_cancels_tool_tasks() -> None:
    cancelled = asyncio.Event()

    @tool
    async def forever() -> str:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return "x"

    @tool
    async def quick() -> str:
        return "q"

    provider = ScriptedProvider(
        [calls(ToolCall(id="1", name="forever"), ToolCall(id="2", name="quick")), text("never")]
    )
    stream = AgentRunner(provider).run_stream(Agent(name="a", tools=(forever, quick)), "go")
    async for event in stream:
        if isinstance(event, ToolCallCompleted):  # quick done, forever still running
            break
    await stream.aclose()
    await asyncio.wait_for(cancelled.wait(), timeout=1)


# ---------------------------------------------------------------------------
# ContextWindow
# ---------------------------------------------------------------------------


def _m(role: str, content: str, **kw: Any) -> Message:
    return Message(role=role, content=content, **kw)  # type: ignore[arg-type]


async def test_context_window_keeps_everything_when_it_fits() -> None:
    msgs = [_m("system", "s"), _m("user", "u1"), _m("assistant", "a1"), _m("user", "u2")]
    assert await ContextWindow().fit(msgs, 100_000) == msgs


async def test_context_window_drops_whole_exchanges_oldest_first() -> None:
    big = "x" * 4_000  # ~1000 tokens
    tool_call = ToolCall(id="t", name="add", arguments={})
    msgs = [
        _m("system", "sys"),
        _m("user", "old " + big),
        _m("assistant", "", tool_calls=(tool_call,)),
        _m("tool", big, tool_call_id="t"),
        _m("assistant", "old answer"),
        _m("user", "recent question"),
        _m("assistant", "recent answer"),
        _m("user", "current"),
    ]
    window = ContextWindow(max_tokens=1_500, reserve_tokens=0)
    fitted = await window.fit(msgs, 128_000)
    assert fitted[0].content == "sys"
    assert fitted[1].role == "system" and "omitted" in fitted[1].content
    assert [m.content for m in fitted[2:]] == ["recent question", "recent answer", "current"]
    assert not any(m.role == "tool" for m in fitted)


async def test_context_window_always_keeps_current_exchange() -> None:
    huge = "y" * 100_000
    msgs = [_m("user", "old"), _m("assistant", "a"), _m("user", huge)]
    fitted = await ContextWindow(max_tokens=1_000, reserve_tokens=0).fit(msgs, 8_000)
    assert fitted[-1].content == huge
    assert all(m.content != "old" for m in fitted)


async def test_context_window_max_messages_and_summarizer() -> None:
    async def summarize(dropped: Sequence[Message]) -> str:
        return f"{len(dropped)} msgs about cooking"

    msgs = [_m("user", f"q{i}") for i in range(6)]
    fitted = await ContextWindow(max_messages=2, summarize=summarize).fit(msgs, 100_000)
    assert fitted[0].content == "Summary of earlier conversation:\n4 msgs about cooking"
    assert [m.content for m in fitted[1:]] == ["q4", "q5"]


# ---------------------------------------------------------------------------
# AgentTool (sub-agents)
# ---------------------------------------------------------------------------


async def test_agent_tool_delegates_and_records_delegation() -> None:
    researcher = Agent(name="researcher", description="Finds facts.", instructions="Research.")
    sub_provider = ScriptedProvider([text("Paris is the capital.")])
    delegate = AgentTool(researcher, AgentRunner(sub_provider))
    assert delegate.name == "delegate_to_researcher"
    assert "Finds facts." in delegate.description

    parent_provider = ScriptedProvider(
        [
            calls(ToolCall(id="d1", name=delegate.name, arguments={"task": "Capital of France?"})),
            text("It's Paris."),
        ]
    )
    ctx = RunContext(run_id="parent", agent_name="lead", user_id="u1")
    events = await collect(
        AgentRunner(parent_provider).run_stream(
            Agent(name="lead", tools=(delegate,)), "q", context=ctx
        )
    )
    result = next(e for e in events if isinstance(e, ToolCallCompleted))
    assert result.output == "Paris is the capital."
    assert result.result.metadata["agent"] == "researcher"
    assert sub_provider.prompts[0][-1].content == "Capital of France?"
    [record] = ctx.state["delegations"]
    assert record["from"] == "lead" and record["to"] == "researcher" and record["success"]


async def test_agent_tool_enforces_depth_limit() -> None:
    delegate = AgentTool(Agent(name="sub"), AgentRunner(ScriptedProvider([])), max_depth=1)
    from agentcook_core.tools import _reset_run_context, _set_run_context

    token = _set_run_context(RunContext(run_id="r", agent_name="a", depth=1))
    try:
        result = await delegate.invoke({"task": "x"})
    finally:
        _reset_run_context(token)
    assert not result.success and "depth limit" in (result.error or "")
    empty = await delegate.invoke({"task": "  "})
    assert not empty.success


def test_event_serialization() -> None:
    call = ToolCall(id="1", name="add", arguments={"a": 1})
    started = ToolCallStarted(call=call, turn=1).to_dict()
    assert started == {
        "type": "tool_call",
        "turn": 1,
        "tool_call": {"id": "1", "name": "add", "arguments": {"a": 1}},
    }
    done = ToolCallCompleted(
        call=call, result=ToolResult(success=True, output=2), output="2", duration_ms=1.234, turn=1
    ).to_dict()
    assert done["type"] == "tool_result" and done["output"] == "2" and done["duration_ms"] == 1.2
