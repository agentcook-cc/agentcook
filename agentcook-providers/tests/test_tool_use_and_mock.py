"""Tool-use wire conversion, streaming usage, fallback safety, MockProvider."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from agentcook_core import (
    Agent,
    AgentRunner,
    ChatChunk,
    LLMProviderProtocol,
    Message,
    RunCompleted,
    TokenUsage,
    ToolCall,
    ToolCallCompleted,
    tool,
)
from agentcook_core.builtin_tools import calculator, current_time
from agentcook_providers import (
    AnthropicProvider,
    EchoProvider,
    FallbackProvider,
    MockProvider,
    OpenAIProvider,
    create_provider,
    create_provider_chain,
)
from agentcook_providers.anthropic_provider import _split_system_messages
from agentcook_providers.openai_provider import _message_to_openai

pytestmark = pytest.mark.unit


@tool
def get_weather(city: str) -> dict[str, str]:
    """Weather for a city."""
    return {"city": city, "weather": "sunny"}


# ---------------------------------------------------------------------------
# Anthropic: message conversion
# ---------------------------------------------------------------------------


def test_anthropic_converts_tool_calls_and_merges_tool_results() -> None:
    msgs = [
        Message(role="system", content="sys"),
        Message(role="user", content="weather in Paris and Rome?"),
        Message(
            role="assistant",
            content="Checking.",
            tool_calls=(
                ToolCall(id="t1", name="get_weather", arguments={"city": "Paris"}),
                ToolCall(id="t2", name="get_weather", arguments={"city": "Rome"}),
            ),
        ),
        Message(role="tool", content='{"w": "sun"}', tool_call_id="t1", name="get_weather"),
        Message(role="tool", content="ERROR: timeout", tool_call_id="t2", name="get_weather"),
        Message(role="assistant", content="Paris is sunny."),
    ]
    system, out = _split_system_messages(msgs)
    assert system == "sys"
    assert [m["role"] for m in out] == ["user", "assistant", "user", "assistant"]
    assert out[1]["content"] == [
        {"type": "text", "text": "Checking."},
        {"type": "tool_use", "id": "t1", "name": "get_weather", "input": {"city": "Paris"}},
        {"type": "tool_use", "id": "t2", "name": "get_weather", "input": {"city": "Rome"}},
    ]
    assert out[2]["content"] == [
        {"type": "tool_result", "tool_use_id": "t1", "content": '{"w": "sun"}'},
        {"type": "tool_result", "tool_use_id": "t2", "content": "ERROR: timeout", "is_error": True},
    ]
    assert out[3] == {"role": "assistant", "content": "Paris is sunny."}


def test_anthropic_merges_consecutive_user_turns() -> None:
    _, out = _split_system_messages(
        [Message(role="user", content="a"), Message(role="user", content="b")]
    )
    assert out == [
        {"role": "user", "content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}
    ]


async def test_anthropic_chat_sends_tools_and_parses_tool_use() -> None:
    reply = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="Let me check."),
            SimpleNamespace(type="tool_use", id="tu_1", name="get_weather", input={"city": "Oslo"}),
        ],
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=5,
            cache_read_input_tokens=90,
            cache_creation_input_tokens=0,
        ),
        stop_reason="tool_use",
    )
    create = AsyncMock(return_value=reply)
    provider = AnthropicProvider(client=SimpleNamespace(messages=SimpleNamespace(create=create)))  # type: ignore[arg-type]
    response = await provider.chat([Message(role="user", content="weather?")], tools=[get_weather])
    sent_tools = create.call_args.kwargs["tools"]
    assert sent_tools[0]["name"] == "get_weather"
    assert sent_tools[0]["input_schema"]["required"] == ["city"]
    assert sent_tools[-1]["cache_control"] == {"type": "ephemeral"}
    assert response.finish_reason == "tool_calls"
    assert response.message.tool_calls == (
        ToolCall(id="tu_1", name="get_weather", arguments={"city": "Oslo"}),
    )
    assert response.usage == TokenUsage(input=100, output=5, cached=90)


class _FakeAnthropicStream:
    def __init__(self, events: list[Any]) -> None:
        self._events = events

    async def __aenter__(self) -> _FakeAnthropicStream:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    def __aiter__(self) -> AsyncIterator[Any]:
        async def gen() -> AsyncIterator[Any]:
            for e in self._events:
                yield e

        return gen()


async def test_anthropic_stream_assembles_tool_use_and_usage() -> None:
    ns = SimpleNamespace
    events = [
        ns(type="message_start", message=ns(usage=ns(input_tokens=20, output_tokens=1))),
        ns(type="content_block_start", index=0, content_block=ns(type="text")),
        ns(type="content_block_delta", index=0, delta=ns(type="text_delta", text="Hm")),
        ns(type="content_block_stop", index=0),
        ns(
            type="content_block_start",
            index=1,
            content_block=ns(type="tool_use", id="tu", name="get_weather"),
        ),
        ns(
            type="content_block_delta",
            index=1,
            delta=ns(type="input_json_delta", partial_json='{"ci'),
        ),
        ns(
            type="content_block_delta",
            index=1,
            delta=ns(type="input_json_delta", partial_json='ty": "Oslo"}'),
        ),
        ns(type="content_block_stop", index=1),
        ns(type="message_delta", delta=ns(stop_reason="tool_use"), usage=ns(output_tokens=17)),
    ]
    client = ns(messages=ns(stream=lambda **kw: _FakeAnthropicStream(events)))
    provider = AnthropicProvider(client=client)  # type: ignore[arg-type]
    chunks = [
        c
        async for c in provider.stream_chat(
            [Message(role="user", content="q")], tools=[get_weather]
        )
    ]
    assert chunks[0].delta_content == "Hm"
    assert chunks[1].delta_tool_calls == (
        ToolCall(id="tu", name="get_weather", arguments={"city": "Oslo"}),
    )
    assert chunks[-1].finish_reason == "tool_calls"
    assert chunks[-1].usage == TokenUsage(input=20, output=17)


# ---------------------------------------------------------------------------
# OpenAI: streaming tool calls + usage
# ---------------------------------------------------------------------------


def _delta(content: str | None = None, tool_calls: Any = None) -> Any:
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _tc(index: int, id: str | None = None, name: str | None = None, args: str | None = None) -> Any:
    return SimpleNamespace(index=index, id=id, function=SimpleNamespace(name=name, arguments=args))


def _chunk(
    delta: Any = None, finish: str | None = None, usage: Any = None, choices: bool = True
) -> Any:
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=delta, finish_reason=finish)] if choices else [],
        usage=usage,
    )


def _openai_with_stream(chunks: list[Any]) -> tuple[OpenAIProvider, AsyncMock]:
    async def agen() -> AsyncIterator[Any]:
        for c in chunks:
            yield c

    create = AsyncMock(return_value=agen())
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return OpenAIProvider(model="gpt-4o-mini", client=client), create  # type: ignore[arg-type]


async def test_openai_stream_assembles_parallel_tool_calls_and_usage() -> None:
    provider, create = _openai_with_stream(
        [
            _chunk(_delta(tool_calls=[_tc(0, "c1", "get_weather", '{"city"')])),
            _chunk(_delta(tool_calls=[_tc(1, "c2", "get_weather", '{"city": "Rome"}')])),
            _chunk(_delta(tool_calls=[_tc(0, None, None, ': "Paris"}')])),
            _chunk(_delta(), finish="tool_calls"),
            _chunk(choices=False, usage=SimpleNamespace(prompt_tokens=30, completion_tokens=12)),
        ]
    )
    chunks = [
        c
        async for c in provider.stream_chat(
            [Message(role="user", content="q")], tools=[get_weather]
        )
    ]
    assert create.call_args.kwargs["stream_options"] == {"include_usage": True}
    calls = [tc for c in chunks for tc in c.delta_tool_calls]
    assert calls == [
        ToolCall(id="c1", name="get_weather", arguments={"city": "Paris"}),
        ToolCall(id="c2", name="get_weather", arguments={"city": "Rome"}),
    ]
    assert chunks[-1].usage == TokenUsage(input=30, output=12)


async def test_openai_stream_emits_tool_calls_even_when_finish_is_stop() -> None:
    provider, _ = _openai_with_stream(
        [
            _chunk(_delta(tool_calls=[_tc(0, "c1", "get_weather", '{"city": "Oslo"}')])),
            _chunk(_delta(), finish="stop"),
        ]
    )
    chunks = [
        c
        async for c in provider.stream_chat(
            [Message(role="user", content="q")], tools=[get_weather]
        )
    ]
    tool_chunk = next(c for c in chunks if c.delta_tool_calls)
    assert tool_chunk.finish_reason == "tool_calls"


async def test_openai_stream_survives_malformed_arguments() -> None:
    provider, _ = _openai_with_stream(
        [_chunk(_delta(tool_calls=[_tc(0, "c1", "get_weather", "{not json")]), finish="tool_calls")]
    )
    chunks = [c async for c in provider.stream_chat([Message(role="user", content="q")])]
    assert chunks[0].delta_tool_calls[0].arguments == {"_raw": "{not json"}


async def test_openai_stream_usage_can_be_disabled() -> None:
    provider, create = _openai_with_stream([_chunk(_delta("hi"), finish="stop")])
    provider._stream_usage = False
    [c async for c in provider.stream_chat([Message(role="user", content="q")])]
    assert "stream_options" not in create.call_args.kwargs


def test_openai_tool_message_omits_name() -> None:
    d = _message_to_openai(Message(role="tool", content="x", name="t", tool_call_id="c"))
    assert d == {"role": "tool", "content": "x", "tool_call_id": "c"}


# ---------------------------------------------------------------------------
# FallbackProvider streaming safety
# ---------------------------------------------------------------------------


class _Flaky:
    def __init__(self, name: str, *, fail_after: int | None, status: int = 503) -> None:
        self._name = name
        self._fail_after = fail_after
        self._status = status

    @property
    def model_name(self) -> str:
        return self._name

    @property
    def context_window(self) -> int:
        return 1000

    def count_tokens(self, text: str) -> int:
        return 1

    async def chat(self, *a: Any, **k: Any) -> Any:  # pragma: no cover
        raise NotImplementedError

    async def stream_chat(self, *a: Any, **k: Any) -> AsyncIterator[ChatChunk]:
        for i in range(3):
            if self._fail_after is not None and i == self._fail_after:
                err = RuntimeError("upstream overloaded")
                err.status_code = self._status  # type: ignore[attr-defined]
                raise err
            yield ChatChunk(delta_content=f"{self._name}{i} ")


async def test_fallback_switches_only_before_first_chunk() -> None:
    chain = FallbackProvider([_Flaky("a", fail_after=0), _Flaky("b", fail_after=None)])
    text = "".join([c.delta_content async for c in chain.stream_chat([])])
    assert text == "b0 b1 b2 "

    mid_stream = FallbackProvider([_Flaky("a", fail_after=2), _Flaky("b", fail_after=None)])
    seen: list[str] = []
    with pytest.raises(RuntimeError, match="overloaded"):
        async for c in mid_stream.stream_chat([]):
            seen.append(c.delta_content)
    assert seen == ["a0 ", "a1 "]  # never spliced with provider b


# ---------------------------------------------------------------------------
# MockProvider
# ---------------------------------------------------------------------------


def test_mock_provider_satisfies_protocol() -> None:
    assert isinstance(MockProvider(), LLMProviderProtocol)


async def test_mock_provider_drives_real_tool_loop() -> None:
    runner = AgentRunner(MockProvider())
    agent = Agent(name="a", tools=(calculator, current_time))
    events = [e async for e in runner.run_stream(agent, "please calculate 1299 * 0.85 - 50")]
    result = next(e for e in events if isinstance(e, ToolCallCompleted))
    assert result.call.name == "calculator"
    assert result.result.output["result"] == 1054.15
    done = events[-1]
    assert isinstance(done, RunCompleted)
    assert "1054.15" in done.output
    assert done.turns == 2


async def test_mock_provider_time_and_chinese() -> None:
    response = await AgentRunner(MockProvider()).run(
        Agent(name="a", tools=(current_time,)), "现在几点？"
    )
    assert response.metadata["tool_calls"] == [{"name": "current_time", "success": True}]
    assert "current_time" in response.output and "Mock" in response.output


async def test_mock_provider_plain_answer_lists_tools() -> None:
    response = await AgentRunner(MockProvider()).run(
        Agent(name="a", tools=(calculator,)), "hello there"
    )
    assert response.metadata["turns"] == 1
    assert "offline mock mode" in response.output
    assert "`calculator`" in response.output


async def test_mock_provider_search_and_skill_rules() -> None:
    @tool
    def web_search(query: str) -> list[str]:
        """Search."""
        return [f"result for {query}"]

    provider = MockProvider()
    text, calls = provider._decide(
        [Message(role="user", content="search bluetooth earbuds")], [web_search]
    )
    assert calls[0].name == "web_search" and calls[0].arguments == {
        "query": "search bluetooth earbuds"
    }

    load_skill = tool(lambda skill: skill, name="load_skill")
    system = Message(role="system", content="## Skills\n- `listing-optimizer`: improve listings")
    _, calls = provider._decide(
        [system, Message(role="user", content="Use the listing optimizer on my product")],
        [load_skill],
    )
    assert calls[0].name == "load_skill" and calls[0].arguments == {"skill": "listing-optimizer"}


async def test_mock_provider_reports_tool_errors() -> None:
    msgs = [
        Message(role="user", content="q"),
        Message(role="assistant", content="", tool_calls=(ToolCall(id="1", name="x"),)),
        Message(role="tool", content="ERROR: boom", name="x", tool_call_id="1"),
    ]
    response = await MockProvider().chat(msgs)
    assert "reported an error: boom" in response.message.content


# ---------------------------------------------------------------------------
# factory
# ---------------------------------------------------------------------------


def test_factory_mock_and_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTCOOK_MOCK_DELAY_MS", "15")
    mock = create_provider("mock")
    assert isinstance(mock, MockProvider) and mock._delay == pytest.approx(0.015)

    single = create_provider_chain("echo")
    assert isinstance(single, EchoProvider)

    chain = create_provider_chain("echo:echo-x, mock")
    assert isinstance(chain, FallbackProvider)
    assert chain.model_name == "echo-x"

    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_provider_chain("nope")
    with pytest.raises(ValueError, match="No usable provider"):
        create_provider_chain(" , ")


async def test_mock_provider_commerce_rules_and_chinese_delegation() -> None:
    sales = tool(lambda product=None: [], name="sales_query")
    rivals = tool(lambda category: [], name="competitor_prices")
    delegate = tool(lambda task: task, name="delegate_to_analyst")
    provider = MockProvider()
    _, calls = provider._decide([Message(role="user", content="看看本月销售数据")], [sales])
    assert calls[0].name == "sales_query"
    _, calls = provider._decide([Message(role="user", content="竞品榨汁机定价")], [rivals])
    assert calls[0].arguments == {"category": "blender"}
    _, calls = provider._decide([Message(role="user", content="请让分析师看看")], [delegate])
    assert calls[0].name == "delegate_to_analyst"
