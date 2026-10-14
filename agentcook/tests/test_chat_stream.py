"""Chat endpoints: the agent loop over HTTP (SSE + JSON + cancel)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Any

import pytest
from agentcook_core import ChatChunk, Message, TokenUsage, ToolCall
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


class Scripted:
    """Provider playing back scripted turns (list of chunk lists)."""

    def __init__(self, turns: list[list[Any]], *, delay: float = 0.0) -> None:
        self.turns = list(turns)
        self.prompts: list[list[Message]] = []
        self.delay = delay

    model_name = "scripted-1"
    context_window = 100_000

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    async def chat(self, *a: Any, **k: Any) -> Any:  # pragma: no cover
        raise NotImplementedError

    async def stream_chat(self, messages: Sequence[Message], **_: Any) -> AsyncIterator[ChatChunk]:
        self.prompts.append(list(messages))
        for chunk in self.turns.pop(0):
            if self.delay:
                await asyncio.sleep(self.delay)
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk


def text_turn(*parts: str) -> list[ChatChunk]:
    return [ChatChunk(delta_content=p) for p in parts] + [
        ChatChunk(finish_reason="stop", usage=TokenUsage(input=11, output=7))
    ]


def tool_turn(name: str, **arguments: Any) -> list[ChatChunk]:
    return [
        ChatChunk(
            delta_tool_calls=(ToolCall(id=f"c-{name}", name=name, arguments=arguments),),
            finish_reason="tool_calls",
        )
    ]


def post_stream(client: TestClient, body: dict[str, Any], **kw: Any) -> Any:
    return client.post("/api/v1/chat/stream", json=body, **kw)


# ---------------------------------------------------------------------------
# Wire format
# ---------------------------------------------------------------------------


class TestWireFormat:
    def test_plain_turn_frames(self, make_app, sse) -> None:
        provider = Scripted([text_turn("Hello", " there")])
        with TestClient(make_app(provider=provider)) as client:
            resp = post_stream(client, {"session_id": "s-1", "message": "hi"})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        frames = sse(resp.text)
        assert [f["type"] for f in frames] == ["start", "delta", "delta", "done"]

        start, *_, done = frames
        assert start["session_id"] == "s-1" and start["run_id"].startswith("run_")
        assert start["metadata"]["agent"] == "assistant"
        assert start["metadata"]["model"] == "scripted-1"
        assert "".join(f["content"] for f in frames) == "Hello there"
        # v1 compatibility fields on every frame
        assert all({"role", "content", "done"} <= f.keys() for f in frames)
        assert done["done"] is True and frames[0]["done"] is False
        meta = done["metadata"]
        assert meta["usage"] == {
            "input_tokens": 11,
            "output_tokens": 7,
            "cached_tokens": 0,
            "total_tokens": 18,
        }
        assert meta["finish_reason"] == "stop" and meta["turns"] == 1
        assert meta["request_id"] == done["run_id"] == start["run_id"]

    def test_tool_call_frames(self, make_app, sse) -> None:
        provider = Scripted([tool_turn("calculator", expression="6*7"), text_turn("42")])
        with TestClient(make_app(provider=provider)) as client:
            frames = sse(post_stream(client, {"session_id": "s", "message": "6*7?"}).text)
        kinds = [f["type"] for f in frames]
        assert kinds == ["start", "tool_call", "tool_result", "delta", "done"]
        call, result = frames[1]["tool_call"], frames[2]["tool_call"]
        assert call == {
            "id": "c-calculator",
            "name": "calculator",
            "arguments": {"expression": "6*7"},
            "status": "running",
            "turn": 1,
        }
        assert result["status"] == "success"
        assert '"result": 42' in result["output"]
        assert frames[2]["tool_calls"] == [result]  # v1 list alias
        assert frames[-1]["metadata"]["turns"] == 2

    def test_mock_model_runs_real_tools_offline(self, client, sse) -> None:
        frames = sse(
            post_stream(client, {"session_id": "s", "message": "calculate 1299 * 0.85 - 50"}).text
        )
        result = next(f for f in frames if f["type"] == "tool_result")
        assert result["tool_call"]["name"] == "calculator"
        assert "1054.15" in "".join(f["content"] for f in frames)
        assert frames[-1]["metadata"]["source"] == "mock"

    def test_provider_failure_becomes_error_frame(self, make_app, sse) -> None:
        provider = Scripted([[ChatChunk(delta_content="par"), RuntimeError("upstream 500")]])
        with TestClient(make_app(provider=provider)) as client:
            frames = sse(post_stream(client, {"session_id": "s", "message": "hi"}).text)
        assert frames[-1]["type"] == "error"
        assert frames[-1]["done"] is True
        assert "RuntimeError: upstream 500" in frames[-1]["error"]


# ---------------------------------------------------------------------------
# Conversation memory across turns
# ---------------------------------------------------------------------------


class TestMultiTurn:
    def test_history_is_replayed_on_next_turn(self, make_app) -> None:
        provider = Scripted(
            [
                tool_turn("calculator", expression="2+2"),
                text_turn("It's 4."),
                text_turn("You asked 2+2."),
            ]
        )
        with TestClient(make_app(provider=provider)) as client:
            post_stream(client, {"session_id": "s", "message": "what is 2+2"})
            post_stream(client, {"session_id": "s", "message": "what did I ask?"})
        second_turn_prompt = provider.prompts[2]
        roles = [m.role for m in second_turn_prompt]
        assert roles == ["system", "user", "assistant", "tool", "assistant", "user"]
        assert second_turn_prompt[-1].content == "what did I ask?"
        assert second_turn_prompt[3].tool_call_id == "c-calculator"

    def test_sessions_are_isolated(self, make_app) -> None:
        provider = Scripted([text_turn("a"), text_turn("b")])
        with TestClient(make_app(provider=provider)) as client:
            post_stream(client, {"session_id": "one", "message": "first"})
            post_stream(client, {"session_id": "two", "message": "second"})
        assert [m.content for m in provider.prompts[1] if m.role == "user"] == ["second"]

    def test_failed_turn_is_persisted_without_breaking_history(self, make_app) -> None:
        provider = Scripted([[RuntimeError("boom")], text_turn("ok")])
        with TestClient(make_app(provider=provider)) as client:
            post_stream(client, {"session_id": "s", "message": "first"})
            post_stream(client, {"session_id": "s", "message": "second"})
            transcript = client.get("/api/v1/conversations/s").json()
        # the error placeholder is not replayed to the model
        assert [m.role for m in provider.prompts[1]] == ["system", "user", "user"]
        assert transcript["messages"][1]["metadata"]["error"].startswith("RuntimeError")


# ---------------------------------------------------------------------------
# Validation + errors
# ---------------------------------------------------------------------------


class TestValidation:
    @pytest.mark.parametrize(
        "body",
        [
            {"session_id": "s"},
            {"message": "hi"},
            {"session_id": "s", "message": ""},
            {"session_id": "", "message": "hi"},
            {"session_id": "has space", "message": "hi"},
            {"session_id": "s", "message": "hi", "unknown": 1},
            {"session_id": "s", "message": "hi", "temperature": 3},
            {"session_id": "s", "message": "hi", "agent": "Bad Name"},
        ],
    )
    def test_invalid_bodies_are_422_envelopes(self, client, body) -> None:
        resp = post_stream(client, body)
        assert resp.status_code == 422
        assert resp.json()["code"] == "INVALID_INPUT"

    def test_unknown_agent_is_404(self, client) -> None:
        resp = post_stream(client, {"session_id": "s", "message": "hi", "agent": "ghost"})
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "AGENT_NOT_FOUND"
        assert "assistant" in body["detail"]["available"]

    def test_unknown_plugin_ids_are_reported_not_fatal(self, client, sse) -> None:
        frames = sse(
            post_stream(
                client, {"session_id": "s", "message": "hi", "plugin_ids": ["web", "nope"]}
            ).text
        )
        assert frames[0]["metadata"]["warnings"] == ["ignored unknown plugin/toolkit id(s): nope"]
        assert frames[-1]["type"] == "done"

    def test_invalid_model_override_is_400(self, client) -> None:
        resp = post_stream(client, {"session_id": "s", "message": "hi", "model": "nope:x"})
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_MODEL"

    def test_model_override_selects_provider(self, client, sse) -> None:
        frames = sse(
            post_stream(client, {"session_id": "s", "message": "hi", "model": "echo"}).text
        )
        assert frames[0]["metadata"]["model"] == "echo-v0"
        assert "".join(f["content"] for f in frames) == "[Echo] hi"

    def test_model_override_ignored_in_production(self, make_app, token, sse) -> None:
        app = make_app(env="production", auth_mode="required")
        with TestClient(app) as client:
            frames = sse(
                post_stream(
                    client,
                    {"session_id": "s", "message": "hi", "model": "echo"},
                    headers={"Authorization": f"Bearer {token()}"},
                ).text
            )
        assert frames[0]["metadata"]["model"] == "mock-agent"

    def test_misconfigured_default_provider_is_503(self, make_app, monkeypatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with TestClient(make_app(llm_provider="anthropic:claude-x")) as client:
            resp = post_stream(client, {"session_id": "s", "message": "hi"})
        assert resp.status_code == 503
        body = resp.json()
        assert body["code"] == "MODEL_UNAVAILABLE"
        assert "ANTHROPIC_API_KEY" in body["message"]

    def test_fallback_chain_skips_unconfigured_provider(self, make_app, monkeypatch, sse) -> None:
        monkeypatch.delenv("QWEN_API_KEY", raising=False)
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        with TestClient(make_app(llm_provider="qwen,mock")) as client:
            frames = sse(post_stream(client, {"session_id": "s", "message": "hi"}).text)
        assert frames[0]["metadata"]["model"] == "mock-agent"


# ---------------------------------------------------------------------------
# Auth + ownership
# ---------------------------------------------------------------------------


class TestAuth:
    def test_optional_mode_allows_anonymous(self, client) -> None:
        assert post_stream(client, {"session_id": "s", "message": "hi"}).status_code == 200

    def test_required_mode_rejects_anonymous(self, make_app) -> None:
        with TestClient(make_app(auth_mode="required")) as client:
            resp = post_stream(client, {"session_id": "s", "message": "hi"})
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_MISSING_TOKEN"

    def test_invalid_token_rejected_even_in_optional_mode(self, client, token) -> None:
        bad = token(secret="some-other-secret-that-is-32-bytes!!")
        resp = post_stream(
            client, {"session_id": "s", "message": "hi"}, headers={"Authorization": f"Bearer {bad}"}
        )
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_INVALID_TOKEN"

    def test_refresh_token_cannot_be_used_as_access_token(self, client, token) -> None:
        refresh = token(typ="refresh")
        resp = post_stream(
            client,
            {"session_id": "s", "message": "hi"},
            headers={"Authorization": f"Bearer {refresh}"},
        )
        assert resp.status_code == 401

    def test_other_users_session_is_not_reachable(self, client, auth) -> None:
        assert (
            post_stream(
                client, {"session_id": "s", "message": "hi"}, headers=auth("alice")
            ).status_code
            == 200
        )
        resp = post_stream(client, {"session_id": "s", "message": "hi"}, headers=auth("mallory"))
        assert resp.status_code == 404
        assert resp.json()["code"] == "SESSION_NOT_FOUND"


# ---------------------------------------------------------------------------
# Non-streaming + cancellation
# ---------------------------------------------------------------------------


class TestJsonAndCancel:
    def test_json_endpoint_returns_full_answer(self, make_app) -> None:
        provider = Scripted([tool_turn("current_time", timezone="UTC"), text_turn("Noon.")])
        with TestClient(make_app(provider=provider)) as client:
            resp = client.post("/api/v1/chat", json={"session_id": "s", "message": "time?"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["content"] == "Noon."
        assert body["agent"] == "assistant"
        assert body["finish_reason"] == "stop"
        assert [t["name"] for t in body["tool_calls"]] == ["current_time"]
        assert body["tool_calls"][0]["status"] == "success"

    def test_cancel_unknown_run_is_404(self, client) -> None:
        resp = client.post("/api/v1/chat/runs/run_0123456789abcdef/cancel")
        assert resp.status_code == 404

    async def test_cancel_stops_run_and_persists_partial_output(self, make_app) -> None:
        from agentcook_app.chat_service import ChatService, ChatTurn
        from agentcook_app.security import UserContext

        provider = Scripted([text_turn(*["word "] * 200)], delay=0.01)
        container = make_app(provider=provider).state.container
        await container.start()
        user = UserContext(user_id="u1", scopes=frozenset())
        try:
            handle = await ChatService(container).start_turn(
                user, ChatTurn(session_id="s", message="go")
            )
            seen: list[dict] = []
            async for frame in handle.frames():
                if frame is None:
                    continue
                seen.append(frame)
                if frame["type"] == "delta" and len([f for f in seen if f["type"] == "delta"]) == 3:
                    assert container.runs.cancel(handle.run_id, user_id="u1")
                    # another user cannot cancel it
                    assert not container.runs.cancel(handle.run_id, user_id="u2")
            transcript = await container.conversations.load_messages("s", user_id="u1")
        finally:
            await container.stop()
        assert seen[-1]["metadata"]["finish_reason"] == "cancelled"
        assert [m.role for m in transcript] == ["user", "assistant"]
        assert transcript[1].metadata["finish_reason"] == "cancelled"
        assert transcript[1].content.startswith("word word word")
        assert container.runs.active_count == 0

    async def test_disconnect_does_not_abort_run(self, make_app) -> None:
        from agentcook_app.chat_service import ChatService, ChatTurn
        from agentcook_app.security import UserContext

        provider = Scripted([text_turn("a ", "b ", "c")], delay=0.01)
        container = make_app(provider=provider).state.container
        await container.start()
        user = UserContext(user_id="u1", scopes=frozenset())
        try:
            handle = await ChatService(container).start_turn(
                user, ChatTurn(session_id="s", message="go")
            )
            async for _frame in handle.frames():
                break  # client goes away after the first frame
            assert handle.task is not None
            await asyncio.wait_for(handle.task, timeout=5)
            transcript = await container.conversations.load_messages("s", user_id="u1")
        finally:
            await container.stop()
        assert transcript[-1].content == "a b c"

    async def test_one_active_run_per_session(self, make_app) -> None:
        from agentcook_app.chat_service import ChatService, ChatTurn
        from agentcook_app.runs import SessionBusyError
        from agentcook_app.security import UserContext

        provider = Scripted([text_turn(*["x "] * 50), text_turn("y")], delay=0.01)
        container = make_app(provider=provider).state.container
        await container.start()
        user = UserContext(user_id="u1", scopes=frozenset())
        service = ChatService(container)
        try:
            first = await service.start_turn(user, ChatTurn(session_id="s", message="1"))
            with pytest.raises(SessionBusyError):
                await service.start_turn(user, ChatTurn(session_id="s", message="2"))
            assert first.task is not None
            await asyncio.wait_for(first.task, timeout=5)
            second = await service.start_turn(user, ChatTurn(session_id="s", message="2"))
            assert second.task is not None
            await asyncio.wait_for(second.task, timeout=5)
        finally:
            await container.stop()
