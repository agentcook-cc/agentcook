"""Delegation graph: catalog topology + recorded sub-agent delegations."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


def test_topology_without_delegations(client: TestClient) -> None:
    body = client.get("/api/v1/agents/assistant/delegations").json()
    assert body["agent_id"] == "assistant"
    assert [n["id"] for n in body["nodes"]] == ["assistant", "researcher", "analyst"]
    assert body["nodes"][0]["role"] == "orchestrator"
    assert body["edges"] == []


def test_recorded_delegation_appears_as_edge(client: TestClient, sse) -> None:
    frames = sse(
        client.post(
            "/api/v1/chat/stream",
            json={"session_id": "d1", "message": "please ask the analyst to check our sales"},
        ).text
    )
    assert any(
        f["type"] == "tool_call" and f["tool_call"]["name"] == "delegate_to_analyst" for f in frames
    )
    body = client.get("/api/v1/agents/assistant/delegations").json()
    [edge] = body["edges"]
    assert edge["from_id"] == "assistant" and edge["to_id"] == "analyst"
    assert edge["status"] == "succeeded"
    assert edge["task"] == "please ask the analyst to check our sales"
    assert edge["started_at"] and edge["completed_at"]
    # the sub-agent's own graph shows the same edge
    sub = client.get("/api/v1/agents/analyst/delegations").json()
    assert [e["id"] for e in sub["edges"]] == [edge["id"]]


def test_delegations_are_private_per_user(client: TestClient, auth) -> None:
    client.post(
        "/api/v1/chat/stream",
        json={"session_id": "d2", "message": "please ask the analyst about pricing"},
        headers=auth("alice"),
    )
    other = client.get("/api/v1/agents/assistant/delegations", headers=auth("bob")).json()
    assert other["edges"] == []


def test_instance_id_resolves_to_agent(client: TestClient) -> None:
    instance = client.get("/api/v1/agents").json()["items"][0]["instance_id"]
    body = client.get(f"/api/v1/agents/{instance}/delegations").json()
    assert body["agent_id"] == instance
    assert body["nodes"][0]["id"] == "assistant"


def test_unknown_agent_is_404(client: TestClient) -> None:
    resp = client.get("/api/v1/agents/ghost/delegations")
    assert resp.status_code == 404
    assert resp.json()["code"] == "AGENT_NOT_FOUND"


def test_invalid_agent_id_is_422(client: TestClient) -> None:
    assert client.get("/api/v1/agents/bad!id/delegations").status_code in (404, 422)
