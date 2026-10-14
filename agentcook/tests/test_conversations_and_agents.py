"""Conversations (transcripts), agent catalog, toolkits, runtime info."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentcook_app.agents import AgentCatalog, AgentSpecError, load_agent_specs, parse_agent_spec
from agentcook_app.routers.conversations import fold_transcript
from agentcook_core import Message, ToolCall
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


def chat(client: TestClient, session: str, message: str, **kw) -> None:
    resp = client.post(
        "/api/v1/chat/stream", json={"session_id": session, "message": message}, **kw
    )
    assert resp.status_code == 200, resp.text


class TestConversations:
    def test_list_get_rename_delete(self, client: TestClient) -> None:
        chat(client, "c1", "calculate 2 + 2")
        chat(client, "c2", "hello")
        listing = client.get("/api/v1/conversations").json()
        assert [c["id"] for c in listing["items"]] == ["c2", "c1"]  # newest first
        assert listing["items"][1]["title"] == "calculate 2 + 2"
        assert listing["items"][1]["message_count"] == 4

        transcript = client.get("/api/v1/conversations/c1").json()
        assert transcript["session"]["id"] == "c1"
        user, assistant = transcript["messages"]
        assert user["role"] == "user" and user["content"] == "calculate 2 + 2"
        assert assistant["role"] == "assistant"
        [call] = assistant["tool_calls"]
        assert call["name"] == "calculator" and call["status"] == "success"
        assert assistant["metadata"]["finish_reason"] == "stop"

        renamed = client.patch("/api/v1/conversations/c1", json={"title": "Math"}).json()
        assert renamed["title"] == "Math"

        assert client.delete("/api/v1/conversations/c1").status_code == 204
        assert client.get("/api/v1/conversations/c1").status_code == 404
        assert client.delete("/api/v1/conversations/c1").status_code == 404

    def test_conversations_are_private(self, client: TestClient, auth) -> None:
        chat(client, "mine", "hi", headers=auth("alice"))
        assert client.get("/api/v1/conversations", headers=auth("bob")).json()["items"] == []
        for method in ("get", "delete"):
            resp = getattr(client, method)("/api/v1/conversations/mine", headers=auth("bob"))
            assert resp.status_code == 404
        resp = client.patch("/api/v1/conversations/mine", json={"title": "x"}, headers=auth("bob"))
        assert resp.status_code == 404
        assert client.get("/api/v1/conversations/mine", headers=auth("alice")).status_code == 200

    def test_title_is_trimmed(self, client: TestClient) -> None:
        chat(client, "long", "word " * 100)
        title = client.get("/api/v1/conversations").json()["items"][0]["title"]
        assert len(title) <= 80 and title.endswith("…")

    def test_fold_transcript_merges_tool_loop_into_one_bubble(self) -> None:
        call = ToolCall(id="t1", name="calculator", arguments={"expression": "1+1"})
        folded = fold_transcript(
            [
                Message(role="user", content="1+1?"),
                Message(role="assistant", content="Let me compute.", tool_calls=(call,)),
                Message(role="tool", content='{"result": 2}', tool_call_id="t1", name="calculator"),
                Message(role="assistant", content="It is 2.", metadata={"finish_reason": "stop"}),
                Message(role="user", content="thanks"),
            ]
        )
        assert [m.role for m in folded] == ["user", "assistant", "user"]
        bubble = folded[1]
        assert bubble.content == "Let me compute.\n\nIt is 2."
        assert bubble.tool_calls[0].status == "success"
        assert bubble.tool_calls[0].output == '{"result": 2}'
        assert bubble.metadata["finish_reason"] == "stop"

    def test_fold_marks_failed_tools(self) -> None:
        call = ToolCall(id="t1", name="x")
        folded = fold_transcript(
            [
                Message(role="user", content="q"),
                Message(role="assistant", content="", tool_calls=(call,)),
                Message(role="tool", content="ERROR: boom", tool_call_id="t1"),
            ]
        )
        assert folded[1].tool_calls[0].status == "error"
        assert folded[1].tool_calls[0].error == "boom"


class TestAgentsCatalog:
    def test_list_agents(self, client: TestClient, auth) -> None:
        body = client.get("/api/v1/agents", headers=auth("alice")).json()
        assert body["default_agent"] == "assistant"
        names = [a["name"] for a in body["items"]]
        assert names[0] == "assistant" and set(names) == {"assistant", "researcher", "analyst"}
        assistant = body["items"][0]
        assert assistant["default"] is True
        assert assistant["memory"] is True
        assert assistant["delegates"] == ["researcher", "analyst"]
        assert assistant["instance_id"].startswith("assistant-")
        bob = client.get("/api/v1/agents", headers=auth("bob")).json()["items"][0]
        assert bob["instance_id"] != assistant["instance_id"]

    def test_agent_detail_lists_effective_tools(self, client: TestClient) -> None:
        body = client.get("/api/v1/agents/assistant").json()
        names = [t["name"] for t in body["tools"]]
        for expected in (
            "current_time",
            "calculator",
            "remember",
            "recall",
            "load_skill",
            "delegate_to_researcher",
            "delegate_to_analyst",
        ):
            assert expected in names
        assert body["instructions"].startswith("You are AgentCook")
        assert client.get("/api/v1/agents/ghost").status_code == 404

    def test_toolkits(self, client: TestClient) -> None:
        items = {k["id"]: k for k in client.get("/api/v1/toolkits").json()["items"]}
        assert set(items) == {"core", "web", "commerce-demo"}
        assert [t["name"] for t in items["web"]["tools"]] == ["fetch_url"]
        assert items["core"]["tools"][1]["parameters"]["required"] == ["expression"]

    def test_runtime_info_has_no_secrets(self, client: TestClient) -> None:
        body = client.get("/api/v1/runtime").json()
        assert body["provider"] == "mock" and body["storage"] == "memory"
        assert "jwt" not in str(body).lower() and "secret" not in str(body).lower()

    def test_chat_with_specific_agent(self, client: TestClient, sse) -> None:
        frames = sse(
            client.post(
                "/api/v1/chat/stream",
                json={
                    "session_id": "a1",
                    "message": "search earbuds trends",
                    "agent": "researcher",
                },
            ).text
        )
        assert frames[0]["metadata"]["agent"] == "researcher"
        call = next(f for f in frames if f["type"] == "tool_call")
        assert call["tool_call"]["name"] == "web_search"


class TestAgentSpecs:
    def test_bundled_specs_are_valid(self) -> None:
        from agentcook_app.config import BUNDLED_AGENTS_DIR

        catalog = AgentCatalog(load_agent_specs(BUNDLED_AGENTS_DIR), default="assistant")
        catalog.validate_toolkits(["core", "web", "commerce-demo"])
        assert catalog.get(None).name == "assistant"

    @pytest.mark.parametrize(
        "raw,message",
        [
            ({"name": "Bad", "instructions": "x"}, "'name' must match"),
            ({"name": "ok"}, "'instructions' is required"),
            ({"name": "ok", "instructions": "x", "toolkits": "core", "bogus": 1}, "unknown field"),
            ({"name": "ok", "instructions": "x", "delegates": [1]}, "list of strings"),
            ({"name": "ok", "instructions": "x", "max_turns": "many"}, "invalid literal"),
        ],
    )
    def test_invalid_specs(self, raw: dict, message: str) -> None:
        with pytest.raises(AgentSpecError, match=message):
            parse_agent_spec(raw)

    def test_catalog_validation(self) -> None:
        a = parse_agent_spec({"name": "a", "instructions": "x", "delegates": ["b"]})
        with pytest.raises(AgentSpecError, match="unknown agent"):
            AgentCatalog([a], default="a")
        self_loop = parse_agent_spec({"name": "a", "instructions": "x", "delegates": ["a"]})
        with pytest.raises(AgentSpecError, match="itself"):
            AgentCatalog([self_loop], default="a")
        with pytest.raises(AgentSpecError, match="default agent"):
            AgentCatalog([parse_agent_spec({"name": "a", "instructions": "x"})], default="z")
        bad_kit = parse_agent_spec({"name": "a", "instructions": "x", "toolkits": ["nope"]})
        with pytest.raises(AgentSpecError, match="unknown toolkit"):
            AgentCatalog([bad_kit], default="a").validate_toolkits(["core"])

    def test_custom_agents_dir(self, make_app, tmp_path: Path, sse) -> None:
        (tmp_path / "support.yaml").write_text(
            "name: support\ninstructions: Help customers.\ntoolkits: [core]\nskills: []\n",
            encoding="utf-8",
        )
        (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
        app = make_app(agents_dir=tmp_path, default_agent="support")
        with TestClient(app) as client:
            assert [a["name"] for a in client.get("/api/v1/agents").json()["items"]] == ["support"]
            frames = sse(
                client.post("/api/v1/chat/stream", json={"session_id": "x", "message": "hi"}).text
            )
            assert frames[0]["metadata"]["agent"] == "support"


class TestMemoryThroughChat:
    def test_remember_then_recall_in_a_new_conversation(self, client: TestClient, sse) -> None:
        chat(client, "m1", "remember that I sell bluetooth earbuds on Amazon")
        frames = sse(
            client.post(
                "/api/v1/chat/stream",
                json={"session_id": "m2", "message": "do you remember what I sell? bluetooth"},
            ).text
        )
        recall = next(f for f in frames if f["type"] == "tool_result")
        assert recall["tool_call"]["name"] == "recall"
        assert "bluetooth earbuds" in recall["tool_call"]["output"]

    def test_memory_instance_is_owned(self, client: TestClient, auth) -> None:
        chat(client, "m1", "remember that my store is called Aura", headers=auth("alice"))
        instance = client.get("/api/v1/agents", headers=auth("alice")).json()["items"][0][
            "instance_id"
        ]
        own = client.get(f"/api/v1/agents/{instance}/memory/events", headers=auth("alice"))
        assert own.status_code == 200
        assert own.json()["items"][0]["content"] == "my store is called Aura"
        foreign = client.get(f"/api/v1/agents/{instance}/memory/events", headers=auth("bob"))
        assert foreign.status_code == 404
        admin = client.get(
            f"/api/v1/agents/{instance}/memory/events", headers=auth("root", scopes="admin")
        )
        assert admin.status_code == 200
