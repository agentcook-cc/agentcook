"""The real-model path: the actual Anthropic SDK against a fake HTTP transport.

Mock mode swaps the model client, so this test is what proves the loop also
works with the SDK's streaming objects (text deltas, tool_use blocks whose
input arrives as partial JSON, usage on message_start / message_delta).
"""

import json

import anthropic
import httpx

from app.agent import core
from app.agent.prompts import SYSTEM_PROMPT
from app.config import settings
from tests.conftest import collect


def sse(*events: dict) -> str:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n" for e in events)


def message_start(input_tokens: int) -> dict:
    message = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "test-model",
        "content": [],
        "stop_reason": None,
        "stop_sequence": None,
        "usage": {"input_tokens": input_tokens, "output_tokens": 1},
    }
    return {"type": "message_start", "message": message}


TOOL_TURN = sse(
    message_start(100),
    {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "我查一下。"}},
    {"type": "content_block_stop", "index": 0},
    {
        "type": "content_block_start",
        "index": 1,
        "content_block": {"type": "tool_use", "id": "toolu_1", "name": "web_search", "input": {}},
    },
    {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": '{"query": "蓝'}},
    {"type": "content_block_delta", "index": 1, "delta": {"type": "input_json_delta", "partial_json": '牙耳机"}'}},
    {"type": "content_block_stop", "index": 1},
    {
        "type": "message_delta",
        "delta": {"stop_reason": "tool_use", "stop_sequence": None},
        "usage": {"output_tokens": 30},
    },
    {"type": "message_stop"},
)

ANSWER_TURN = sse(
    message_start(300),
    {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "降噪是"}},
    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "标配了。"}},
    {"type": "content_block_stop", "index": 0},
    {
        "type": "message_delta",
        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": 12},
    },
    {"type": "message_stop"},
)


def test_full_turn_through_the_sdk(monkeypatch):
    monkeypatch.setattr(settings, "model_name", "pinned-model")
    requests: list[dict] = []
    replies = [TOOL_TURN, ANSWER_TURN]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/messages"
        requests.append(json.loads(request.content))
        return httpx.Response(200, text=replies.pop(0), headers={"content-type": "text/event-stream"})

    client = anthropic.AsyncAnthropic(
        api_key="test", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    events = collect(core.run_agent("蓝牙耳机有什么新品？", "sdk", llm=client))

    text = "".join(e["content"] for e in events if e["type"] == "text")
    assert text == "我查一下。降噪是标配了。"
    call = next(e for e in events if e["type"] == "tool_call")
    assert call == {"type": "tool_call", "id": "toolu_1", "name": "web_search", "input": {"query": "蓝牙耳机"}}
    result = next(e for e in events if e["type"] == "tool_result")
    assert result["is_error"] is False and result["result"]["source"] == "mock"
    assert events[-1] == {
        "type": "done",
        "rounds": 2,
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 400, "output_tokens": 42},
    }

    first, second = requests
    assert first["model"] == "pinned-model" and first["stream"] is True and first["system"] == SYSTEM_PROMPT
    assert {t["name"] for t in first["tools"]} >= {"web_search", "data_query"}
    assert first["messages"] == [{"role": "user", "content": "蓝牙耳机有什么新品？"}]
    assert second["messages"][1] == {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "我查一下。"},
            {"type": "tool_use", "id": "toolu_1", "name": "web_search", "input": {"query": "蓝牙耳机"}},
        ],
    }
    tool_result = second["messages"][2]["content"][0]
    assert tool_result["type"] == "tool_result" and tool_result["tool_use_id"] == "toolu_1"
    assert json.loads(tool_result["content"])["query"] == "蓝牙耳机"


def test_model_is_resolved_from_the_models_api_when_not_set():
    seen_models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            models = [
                {
                    "type": "model",
                    "id": f"claude-{family}-test",
                    "display_name": family,
                    "created_at": "2026-01-01T00:00:00Z",
                }
                for family in ("opus", "sonnet", "haiku")
            ]
            return httpx.Response(200, json={"data": models, "has_more": False, "first_id": None, "last_id": None})
        seen_models.append(json.loads(request.content)["model"])
        return httpx.Response(200, text=ANSWER_TURN, headers={"content-type": "text/event-stream"})

    client = anthropic.AsyncAnthropic(
        api_key="test", http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    collect(core.run_agent("hi", "auto", llm=client))
    collect(core.run_agent("again", "auto", llm=client))
    assert seen_models == ["claude-sonnet-test", "claude-sonnet-test"]  # looked up once, then cached


def test_api_errors_are_explained(monkeypatch):
    monkeypatch.setattr(settings, "model_name", "pinned-model")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, json={"type": "error", "error": {"type": "authentication_error", "message": "bad key"}}
        )

    client = anthropic.AsyncAnthropic(
        api_key="bad", max_retries=0, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    events = collect(core.run_agent("hi", "sdk-err", llm=client))
    assert events == [{"type": "error", "message": "模型 API Key 无效或已过期，请检查 ANTHROPIC_API_KEY"}]
    assert core.sessions.get("sdk-err").get_messages() == []
