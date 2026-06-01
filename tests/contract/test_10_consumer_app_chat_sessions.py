"""Consumer-side Pact: agentcook-app → agentcook-chat (chat/stream) & agentcook-java-app (sessions/plugins).

Day 35-37 — adds contract coverage for the two remaining app-facing surfaces:

1. **Chat streaming** (Python FastAPI): POST /api/v1/chat/stream — SSE endpoint
   where the React chat UI sends user messages and receives token-by-token
   replies. Pact validates request shape + 200 status; SSE frame parsing is
   e2e territory.

2. **Sessions CRUD** (Java Spring Boot): GET/POST /api/v1/sessions — the app's
   session sidebar lists existing conversations and creates new ones.

3. **Plugin catalog** (Java Spring Boot): GET /api/v1/plugins — the app's
   plugin picker shows available plugins the user can attach to a chat turn.

Why split into two logical providers under one file:
    The chat endpoint lives in the Python runtime (`agentcook`), while sessions
    and plugins are served by the Java gateway (`agentcook-java`). Pact v3 keys
    contracts by `(consumer, provider)` tuple, so we need two separate Pact
    builders. Both write their own JSON into `pacts_dir`; the provider verify
    CI job pulls every contract whose provider name matches the running service.

SSE note:
    Pact's mock server cannot replay a true `text/event-stream`. The contract
    here asserts that the consumer sends the right JSON envelope and accepts
    a 200 response. The actual SSE chunk parsing is covered by the e2e spec
    `e2e/app/chat.spec.ts`.
"""

from __future__ import annotations

import httpx
import pytest
from pact.v3 import Pact


# ============================================================================
# Part 1: agentcook-app → agentcook-chat  (Python chat/stream)
# ============================================================================

CHAT_CONSUMER = "agentcook-app"
CHAT_PROVIDER = "agentcook-chat"


@pytest.mark.contract
def test_app_chat_stream_contract(pacts_dir):
    """POST /api/v1/chat/stream — send a message and expect SSE stream."""
    pact = Pact(CHAT_CONSUMER, CHAT_PROVIDER).with_specification("V3")

    (
        pact.upon_receiving("send a chat message and stream reply")
        .given("session sess-001 exists with agent agt-001")
        .with_request(
            method="POST",
            path="/api/v1/chat/stream",
        )
        .with_body(
            content_type="application/json",
            body={
                "session_id": "sess-001",
                "message": "What are the pricing tiers?",
                "plugin_ids": ["plugin-translate"],
            },
        )
        .will_respond_with(200)
    )

    with pact.serve() as mock:
        r = httpx.post(
            f"{mock.url}/api/v1/chat/stream",
            json={
                "session_id": "sess-001",
                "message": "What are the pricing tiers?",
                "plugin_ids": ["plugin-translate"],
            },
        )
        assert r.status_code == 200

    pact.write_file(str(pacts_dir), overwrite=True)


# ============================================================================
# Part 2: agentcook-app → agentcook-java-app  (sessions + plugins)
# ============================================================================

JAVA_CONSUMER = "agentcook-app"
JAVA_PROVIDER = "agentcook-java-app"


@pytest.mark.contract
def test_app_sessions_and_plugins_contract(pacts_dir):
    """GET/POST /api/v1/sessions + GET /api/v1/plugins — session sidebar & plugin picker."""
    pact = Pact(JAVA_CONSUMER, JAVA_PROVIDER).with_specification("V3")

    # --- Interaction 1: list sessions for a user ---------------------
    (
        pact.upon_receiving("list sessions for user usr-001")
        .given("user usr-001 has two existing sessions")
        .with_request(
            method="GET",
            path="/api/v1/sessions",
        )
        .with_query_parameter("userId", "usr-001")
        .will_respond_with(200)
        .with_body(
            content_type="application/json",
            body={
                "items": [
                    {
                        "id": "sess-001",
                        "title": "Pricing discussion",
                        "agent_id": "agt-001",
                        "created_at": "2026-05-20T10:00:00Z",
                        "updated_at": "2026-05-21T15:30:00Z",
                    },
                    {
                        "id": "sess-002",
                        "title": "Feature comparison",
                        "agent_id": "agt-002",
                        "created_at": "2026-05-19T08:00:00Z",
                        "updated_at": "2026-05-19T09:15:00Z",
                    },
                ],
                "total": 2,
            },
        )
    )

    # --- Interaction 2: create a new session -------------------------
    (
        pact.upon_receiving("create a new session for user usr-001")
        .given("agent agt-001 is available")
        .with_request(
            method="POST",
            path="/api/v1/sessions",
        )
        .with_body(
            content_type="application/json",
            body={
                "user_id": "usr-001",
                "agent_id": "agt-001",
                "title": "New conversation",
            },
        )
        .will_respond_with(201)
        .with_body(
            content_type="application/json",
            body={
                "id": "sess-003",
                "title": "New conversation",
                "agent_id": "agt-001",
                "user_id": "usr-001",
                "created_at": "2026-05-21T19:00:00Z",
                "updated_at": "2026-05-21T19:00:00Z",
            },
        )
    )

    # --- Interaction 3: list available plugins -----------------------
    (
        pact.upon_receiving("list available plugins for plugin picker")
        .given("three plugins are registered")
        .with_request(
            method="GET",
            path="/api/v1/plugins",
        )
        .will_respond_with(200)
        .with_body(
            content_type="application/json",
            body={
                "items": [
                    {
                        "id": "plugin-translate",
                        "name": "Translate",
                        "description": "Translate messages to another language.",
                        "category": "utility",
                    },
                    {
                        "id": "plugin-summarize",
                        "name": "Summarize",
                        "description": "Summarize long conversations.",
                        "category": "memory",
                    },
                    {
                        "id": "plugin-code-explain",
                        "name": "Code Explain",
                        "description": "Explain code snippets in natural language.",
                        "category": "dev",
                    },
                ],
                "total": 3,
            },
        )
    )

    with pact.serve() as mock:
        # Interaction 1 — list sessions
        r1 = httpx.get(f"{mock.url}/api/v1/sessions", params={"userId": "usr-001"})
        assert r1.status_code == 200
        body1 = r1.json()
        assert "items" in body1 and isinstance(body1["items"], list)
        assert len(body1["items"]) == 2
        assert body1["items"][0]["id"] == "sess-001"

        # Interaction 2 — create session
        r2 = httpx.post(
            f"{mock.url}/api/v1/sessions",
            json={
                "user_id": "usr-001",
                "agent_id": "agt-001",
                "title": "New conversation",
            },
        )
        assert r2.status_code == 201
        assert r2.json()["id"] == "sess-003"

        # Interaction 3 — list plugins
        r3 = httpx.get(f"{mock.url}/api/v1/plugins")
        assert r3.status_code == 200
        body3 = r3.json()
        assert "items" in body3 and isinstance(body3["items"], list)
        assert body3["items"][0]["id"] == "plugin-translate"

    pact.write_file(str(pacts_dir), overwrite=True)
