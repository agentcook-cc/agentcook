"""Consumer Pact: agentcook-app → agentcook (Python agent runtime).

What the React chat app calls on the runtime (see ``agentcook-app/src/api/runtime.ts``
and ``hooks/useAgentChat.ts``):

1. ``GET  /api/v1/runtime``       — mock-model badge, auth mode, default agent
2. ``GET  /api/v1/agents``        — AgentPicker
3. ``GET  /api/v1/toolkits``      — tool picker
4. ``POST /api/v1/chat/stream``   — one chat turn, answered as Server-Sent Events

The app runs anonymously when the runtime's auth mode allows it, so no
Authorization header is required here. Pact can't replay an SSE body, so the
chat interaction pins the request envelope, the status and the content
type; the frame protocol itself is covered by the runtime's
``test_chat_stream.py`` and the Playwright ``agent-chat.spec.ts``.

Verified without a broker by ``test_11_provider_verify_local.py``.
"""

from __future__ import annotations

import httpx
import pytest
from pact.v3 import Pact, match

CONSUMER = "agentcook-app"
PROVIDER = "agentcook"

AGENT = {
    "name": "assistant",
    "title": "AgentCook Assistant",
    "description": "General-purpose assistant.",
    "default": True,
    "toolkits": ["core"],
    "delegates": ["researcher", "analyst"],
}
TOOLKIT = {
    "id": "core",
    "name": "Core utilities",
    "description": "Current time and exact arithmetic.",
    "tools": match.each_like(
        {"name": "calculator", "description": "Evaluate an arithmetic expression."}
    ),
}


@pytest.mark.contract
def test_app_runtime_contract(pacts_dir):
    pact = Pact(CONSUMER, PROVIDER).with_specification("V3")

    (
        pact.upon_receiving("runtime info for the chat page")
        .with_request("GET", "/api/v1/runtime")
        .will_respond_with(200)
        .with_body(
            match.like(
                {
                    "version": "2.0.0",
                    "mock_model": True,
                    "auth_mode": "optional",
                    "default_agent": "assistant",
                    "agents": ["assistant"],
                }
            ),
            content_type="application/json",
        )
    )
    (
        pact.upon_receiving("the agents a user can talk to")
        .with_request("GET", "/api/v1/agents")
        .will_respond_with(200)
        .with_body(
            {"items": match.each_like(match.like(AGENT), min=1)}, content_type="application/json"
        )
    )
    (
        pact.upon_receiving("the toolkits a user can enable")
        .with_request("GET", "/api/v1/toolkits")
        .will_respond_with(200)
        .with_body(
            {"items": match.each_like(match.like(TOOLKIT), min=1)}, content_type="application/json"
        )
    )
    (
        pact.upon_receiving("one chat turn streamed as SSE")
        .with_request("POST", "/api/v1/chat/stream")
        .with_body(
            {"session_id": "c-contract-0001", "message": "what time is it?", "agent": "assistant"},
            content_type="application/json",
        )
        .will_respond_with(200)
        .with_header(
            "Content-Type",
            match.regex("text/event-stream; charset=utf-8", regex=r"^text/event-stream.*"),
        )
    )

    with pact.serve() as mock:
        info = httpx.get(f"{mock.url}/api/v1/runtime").json()
        assert info["default_agent"] == "assistant"
        assert httpx.get(f"{mock.url}/api/v1/agents").json()["items"][0]["name"] == "assistant"
        assert httpx.get(f"{mock.url}/api/v1/toolkits").json()["items"][0]["tools"][0]["name"]
        chat = httpx.post(
            f"{mock.url}/api/v1/chat/stream",
            json={
                "session_id": "c-contract-0001",
                "message": "what time is it?",
                "agent": "assistant",
            },
        )
        assert chat.status_code == 200

    pact.write_file(str(pacts_dir), overwrite=True)
