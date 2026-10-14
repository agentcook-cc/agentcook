"""The ReAct loop, driven by a scripted model so every branch is deterministic."""

import asyncio
import json

import pytest

from app.agent import core
from app.agent.context import ContextManager
from app.agent.mock_llm import Message, MockLLM, TextBlock, ToolUseBlock, Usage, _Stream
from app.config import settings
from app.tools.base import BaseTool
from app.tools.registry import tool_registry
from tests.conftest import collect


class ScriptedLLM:
    """Replies with the next scripted message on each call and records what it was sent."""

    def __init__(self, *replies: list):
        self.replies = list(replies)
        self.calls: list[dict] = []
        self.messages = self

    def stream(self, **kwargs):
        self.calls.append({**kwargs, "messages": json.loads(json.dumps(kwargs["messages"]))})
        content = self.replies.pop(0)
        stop = "tool_use" if any(b.type == "tool_use" for b in content) else "end_turn"
        return _Stream(Message(content, stop, Usage(10, 5)), delay=0)


class FailingLLM:
    def __init__(self):
        self.messages = self

    def stream(self, **kwargs):
        raise RuntimeError("upstream exploded")


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo the input."
    parameters = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}

    async def execute(self, text: str = "", **kwargs):
        return {"echo": text}


class SlowTool(EchoTool):
    name = "slow"

    async def execute(self, **kwargs):
        await asyncio.sleep(5)


class BoomTool(EchoTool):
    name = "boom"

    async def execute(self, **kwargs):
        raise ValueError("kaput")


def call(name: str, **args) -> ToolUseBlock:
    return ToolUseBlock(id=f"toolu_{name}", name=name, input=args)


def types(events: list[dict]) -> list[str]:
    """Event types, with consecutive text chunks collapsed into one."""
    out: list[str] = []
    for e in events:
        if not (e["type"] == "text" and out and out[-1] == "text"):
            out.append(e["type"])
    return out


def test_plain_answer_streams_text_then_done():
    llm = ScriptedLLM([TextBlock("Hello there!")])
    events = collect(core.run_agent("hi", "s1", llm=llm))
    assert "".join(e["content"] for e in events if e["type"] == "text") == "Hello there!"
    assert events[-1] == {
        "type": "done",
        "rounds": 1,
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    assert llm.calls[0]["messages"] == [{"role": "user", "content": "hi"}]


def test_tool_round_trip_feeds_results_back_to_the_model():
    tool_registry.register(EchoTool())
    llm = ScriptedLLM([TextBlock("Let me check."), call("echo", text="ping")], [TextBlock("It said ping.")])
    events = collect(core.run_agent("echo ping", "s1", llm=llm))

    assert types(events) == ["text", "tool_call", "tool_result", "text", "done"]
    by_type = {e["type"]: e for e in events}
    assert by_type["tool_call"] == {"type": "tool_call", "id": "toolu_echo", "name": "echo", "input": {"text": "ping"}}
    assert by_type["tool_result"]["result"] == {"echo": "ping"} and by_type["tool_result"]["is_error"] is False
    assert events[-1]["rounds"] == 2

    second = llm.calls[1]["messages"]
    assert second[1]["content"][1] == {
        "type": "tool_use",
        "id": "toolu_echo",
        "name": "echo",
        "input": {"text": "ping"},
    }
    assert second[2] == {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": "toolu_echo", "content": '{"echo": "ping"}', "is_error": False}
        ],
    }
    assert any(t["name"] == "echo" for t in llm.calls[0]["tools"])


def test_tool_failures_become_error_results_not_crashes(monkeypatch):
    monkeypatch.setattr(settings, "tool_timeout_seconds", 0.05)
    for tool in (SlowTool(), BoomTool()):
        tool_registry.register(tool)
    llm = ScriptedLLM([call("slow"), call("boom"), call("missing")], [TextBlock("Sorry.")])
    events = collect(core.run_agent("go", "s1", llm=llm))

    results = {e["name"]: e for e in events if e["type"] == "tool_result"}
    assert results["slow"]["is_error"] and "超时" in results["slow"]["result"]["error"]
    assert results["boom"]["is_error"] and "kaput" in results["boom"]["result"]["error"]
    assert results["missing"]["is_error"] and "未知工具" in results["missing"]["result"]["error"]
    assert events[-1]["type"] == "done"
    sent = llm.calls[1]["messages"][-1]["content"]
    assert [r["is_error"] for r in sent] == [True, True, True]


def test_long_tool_output_is_truncated_for_the_model(monkeypatch):
    monkeypatch.setattr(settings, "max_tool_result_chars", 50)
    tool_registry.register(EchoTool())
    llm = ScriptedLLM([call("echo", text="x" * 500)], [TextBlock("ok")])
    events = collect(core.run_agent("go", "s1", llm=llm))
    sent = llm.calls[1]["messages"][-1]["content"][0]["content"]
    assert sent.startswith('{"echo": "xxx') and "结果已截断" in sent and len(sent) < 100
    result_event = next(e for e in events if e["type"] == "tool_result")
    assert isinstance(result_event["result"], str)


def test_round_limit_closes_the_turn_cleanly(monkeypatch):
    monkeypatch.setattr(settings, "max_reasoning_rounds", 2)
    tool_registry.register(EchoTool())
    llm = ScriptedLLM([call("echo", text="1")], [call("echo", text="2")], [TextBlock("next turn")])
    events = collect(core.run_agent("loop", "s1", llm=llm))
    assert events[-1]["stop_reason"] == "max_rounds"
    history = core.sessions.get("s1").get_messages()
    assert history[-1]["role"] == "assistant"  # never ends on a dangling tool_result

    collect(core.run_agent("again", "s1", llm=llm))
    assert llm.calls[-1]["messages"][-1] == {"role": "user", "content": "again"}


def test_history_persists_across_turns():
    llm = ScriptedLLM([TextBlock("first")], [TextBlock("second")])
    collect(core.run_agent("one", "s1", llm=llm))
    collect(core.run_agent("two", "s1", llm=llm))
    assert [m["role"] for m in llm.calls[1]["messages"]] == ["user", "assistant", "user"]
    collect(core.run_agent("other", "s2", llm=ScriptedLLM([TextBlock("x")])))
    assert len(core.sessions.get("s1")) == 4


def test_failed_turn_is_rolled_back_and_reported():
    events = collect(core.run_agent("hi", "s1", llm=FailingLLM()))
    assert events == [{"type": "error", "message": "出错了：RuntimeError: upstream exploded"}]
    assert core.sessions.get("s1").get_messages() == []


def test_busy_session_rejects_a_second_concurrent_turn():
    async def scenario():
        slow = MockLLM(delay=0.01)
        first = core.run_agent("hello", "s1", llm=slow)
        first_event = await first.__anext__()  # first turn now holds the session lock
        second = [json.loads(e) async for e in core.run_agent("again", "s1", llm=slow)]
        rest = [json.loads(e) async for e in first]
        return json.loads(first_event), second, rest

    first_event, second, rest = asyncio.run(scenario())
    assert first_event["type"] == "text"
    assert second == [{"type": "error", "message": "这个会话正在生成回复，请等它结束再发"}]
    assert rest[-1]["type"] == "done"


def test_missing_api_key_is_a_clear_error(monkeypatch):
    monkeypatch.setattr(settings, "mock_mode", False)
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(core, "_llm", None)
    events = collect(core.run_agent("hi", "s1"))
    assert events[0]["type"] == "error" and "ANTHROPIC_API_KEY" in events[0]["message"]


@pytest.mark.parametrize(
    ("message", "tool"),
    [("搜索一下蓝牙耳机最近有什么热门新品", "web_search"), ("最近7天哪个商品卖得最好？", "data_query")],
)
def test_mock_model_drives_the_real_loop(message, tool):
    events = collect(core.run_agent(message, "s1"))
    assert types(events)[-1] == "done"
    call_event = next(e for e in events if e["type"] == "tool_call")
    result_event = next(e for e in events if e["type"] == "tool_result")
    assert call_event["name"] == tool and result_event["is_error"] is False
    answer = "".join(e["content"] for e in events if e["type"] == "text")
    assert tool in answer and "Mock" in answer


def test_mock_model_without_matching_tool_explains_itself():
    events = collect(core.run_agent("你好", "s1"))
    assert types(events)[-1] == "done" and "tool_call" not in types(events)
    assert "web_search" in "".join(e["content"] for e in events if e["type"] == "text")


class TestContextManager:
    def test_trim_keeps_first_message_and_recent_history(self):
        ctx = ContextManager("s", max_messages=5)
        for i in range(6):
            ctx.add_user_message(f"q{i}")
            ctx.add_assistant_message(f"a{i}")
        ctx.add_user_message("latest")  # trimming happens as a new turn starts
        messages = ctx.get_messages()
        assert len(messages) <= 5
        assert messages[0]["content"] == "q0"
        assert [m["content"] for m in messages[1:]] == ["q4", "a4", "q5", "a5", "latest"][-(len(messages) - 1) :]
        assert messages[1]["role"] == "user"

    def test_trim_never_starts_the_tail_on_an_orphaned_tool_result(self):
        ctx = ContextManager("s", max_messages=4)
        ctx.add_user_message("first")
        ctx.add_assistant_message([{"type": "tool_use", "id": "t1", "name": "x", "input": {}}])
        ctx.add_tool_results([{"type": "tool_result", "tool_use_id": "t1", "content": "r"}])
        ctx.add_assistant_message("answer")
        ctx.add_user_message("second")
        messages = ctx.get_messages()
        # A naive "first + last 3" would keep the tool_result without its tool_use.
        assert messages == [{"role": "user", "content": "first"}, {"role": "user", "content": "second"}]

    def test_rollback_restores_the_snapshot(self):
        ctx = ContextManager("s")
        ctx.add_user_message("kept")
        snapshot = ctx.checkpoint()
        ctx.add_user_message("dropped")
        ctx.rollback(snapshot)
        assert ctx.get_messages() == [{"role": "user", "content": "kept"}]


def test_session_store_evicts_least_recently_used():
    store = core.SessionStore(max_sessions=2)
    a = store.get("a")
    store.get("b")
    store.get("a")
    store.get("c")
    assert store.get("a") is a
    assert "b" not in store._sessions
