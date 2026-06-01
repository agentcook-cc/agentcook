"""Tests for the agentcook FastAPI runtime.

Coverage strategy:
- Auth + envelope shape: 3 token-failure paths.
- Per-endpoint: happy path (200/201) + 404 + business-rule edge (e.g. 412 / 422).
- Cross-cutting: CORS preflight, OpenAPI completeness, request_id header.

Each test owns an isolated :class:`InMemoryAgentRuntime`, injected via
``app.dependency_overrides`` so tests don't share state.
"""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Iterator

import jwt
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

os.environ.setdefault("AGENTCOOK_JWT_SECRET", "test-secret-do-not-use-anywhere-else")

from agentcook_app.main import create_app  # noqa: E402
from agentcook_app.services import (  # noqa: E402
    InMemoryAgentRuntime,
    get_runtime,
)
from agentcook_core import IdentityCard  # noqa: E402

_AGENT = "agent-1"
_USER = "user-1"


def _token(*, expired: bool = False, claims: dict | None = None) -> str:
    base: dict = {
        "sub": _USER,
        "scopes": "agent:read agent:write",
        "exp": dt.datetime.now(tz=dt.UTC)
        + dt.timedelta(minutes=-5 if expired else 15),
    }
    if claims:
        base.update(claims)
    return jwt.encode(base, os.environ["AGENTCOOK_JWT_SECRET"], algorithm="HS256")


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token()}"}


def _confirm_auth() -> dict[str, str]:
    return {**_auth(), "X-Confirm-Identity-Change": "true"}


@pytest.fixture
def fake_runtime() -> InMemoryAgentRuntime:
    runtime = InMemoryAgentRuntime()
    runtime.seed_agent(
        IdentityCard(
            name=_AGENT,
            role="assistant",
            created_at="2026-05-21T00:00:00+00:00",
            scopes=frozenset({"chat", "search"}),
            metadata={"team": "qa"},
        ),
        agent_id=_AGENT,
    )
    return runtime


@pytest.fixture
def client(fake_runtime: InMemoryAgentRuntime) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_runtime] = lambda: fake_runtime
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# --------------------------- meta / health ---------------------------

# Endpoint renamed Day 20: `setup_health(app)` registers `/health` (liveness)
# and `/health/ready` (readiness). The legacy `/healthz` was removed.

def test_health_is_open(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200 and resp.json() == {"status": "ok"}


def test_request_id_header_is_set(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.headers.get("x-request-id")


def test_health_ready_returns_503_when_dependencies_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Readiness fails closed when postgres or redis is unreachable.

    Stubs the dependency probes so the test doesn't depend on whatever
    happens to be listening on the host's :5432/:6379 — `make dev` may or
    may not be running. The probes are looked up by name on every request
    in `setup_health`, so monkeypatching the module attribute takes effect
    even though `client` was created earlier.
    """
    from agentcook_app import health as health_mod

    async def _down() -> tuple[bool, str]:
        return False, "stub: dependency down"

    monkeypatch.setattr(health_mod, "_check_postgres", _down)
    monkeypatch.setattr(health_mod, "_check_redis", _down)

    resp = client.get("/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["postgres"]["status"] == "down"
    assert body["checks"]["redis"]["status"] == "down"


def test_cors_preflight_allows_admin_origin(client: TestClient) -> None:
    resp = client.options(
        f"/api/v1/agents/{_AGENT}/identity",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"


# --------------------------- auth envelopes ---------------------------

def test_endpoint_without_token_returns_envelope(client: TestClient) -> None:
    resp = client.get(f"/api/v1/agents/{_AGENT}/identity")
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_MISSING_TOKEN"


def test_endpoint_with_expired_token_returns_envelope(client: TestClient) -> None:
    resp = client.get(
        f"/api/v1/agents/{_AGENT}/identity",
        headers={"Authorization": f"Bearer {_token(expired=True)}"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_TOKEN_EXPIRED"


def test_endpoint_with_bad_token_returns_envelope(client: TestClient) -> None:
    resp = client.get(
        f"/api/v1/agents/{_AGENT}/identity",
        headers={"Authorization": "Bearer not.a.real.token"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "AUTH_INVALID_TOKEN"


# --------------------------- Identity ---------------------------

def test_get_identity_happy_path(client: TestClient) -> None:
    resp = client.get(f"/api/v1/agents/{_AGENT}/identity", headers=_auth())
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == _AGENT and body["role"] == "assistant"
    assert sorted(body["scopes"]) == ["chat", "search"]
    assert body["metadata"] == {"team": "qa"}


def test_get_identity_unknown_agent_returns_404_envelope(client: TestClient) -> None:
    resp = client.get("/api/v1/agents/agent-ghost/identity", headers=_auth())
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "AGENT_NOT_FOUND"
    assert body["detail"]["agent_id"] == "agent-ghost"


def test_agent_id_pattern_validation(client: TestClient) -> None:
    resp = client.get("/api/v1/agents/has spaces/identity", headers=_auth())
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_INPUT"


# --------------------------- Soul: GET latest ---------------------------

def test_get_soul_latest_404_when_uninitialized(client: TestClient) -> None:
    resp = client.get(f"/api/v1/agents/{_AGENT}/soul", headers=_auth())
    assert resp.status_code == 404
    assert resp.json()["code"] == "SOUL_NOT_INITIALIZED"


def test_get_soul_latest_after_append(client: TestClient) -> None:
    body = {"tone": "warm", "language_style": "friendly", "values": ["clarity"]}
    client.post(
        f"/api/v1/agents/{_AGENT}/soul",
        headers=_confirm_auth(),
        json=body,
    )
    resp = client.get(f"/api/v1/agents/{_AGENT}/soul", headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["tone"] == "warm"


# --------------------------- Soul: POST append ---------------------------

def test_append_soul_requires_confirmation_header(client: TestClient) -> None:
    resp = client.post(
        f"/api/v1/agents/{_AGENT}/soul",
        headers=_auth(),
        json={"tone": "warm", "language_style": "friendly"},
    )
    assert resp.status_code == 412
    assert resp.json()["code"] == "CONFIRMATION_REQUIRED"


def test_append_soul_creates_versions_incrementally(client: TestClient) -> None:
    for tone in ("warm", "precise", "playful"):
        resp = client.post(
            f"/api/v1/agents/{_AGENT}/soul",
            headers=_confirm_auth(),
            json={"tone": tone, "language_style": "concise"},
        )
        assert resp.status_code == 201
    history = client.get(
        f"/api/v1/agents/{_AGENT}/soul/history", headers=_auth()
    ).json()
    assert [v["version"] for v in history["items"]] == [1, 2, 3]
    assert history["items"][-1]["config"]["tone"] == "playful"


def test_append_soul_unknown_agent_returns_404(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/agents/agent-ghost/soul",
        headers=_confirm_auth(),
        json={"tone": "warm", "language_style": "friendly"},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "AGENT_NOT_FOUND"


# --------------------------- Soul: GET history ---------------------------

def test_get_soul_history_empty_when_uninitialized(client: TestClient) -> None:
    resp = client.get(f"/api/v1/agents/{_AGENT}/soul/history", headers=_auth())
    assert resp.status_code == 200 and resp.json() == {"items": []}


def test_get_soul_history_respects_limit(client: TestClient) -> None:
    for tone in ("a", "b", "c"):
        client.post(
            f"/api/v1/agents/{_AGENT}/soul",
            headers=_confirm_auth(),
            json={"tone": tone, "language_style": "concise"},
        )
    resp = client.get(
        f"/api/v1/agents/{_AGENT}/soul/history?limit=2", headers=_auth()
    )
    assert len(resp.json()["items"]) == 2


# --------------------------- Memory events: POST append ---------------------------

def test_append_memory_event_assigns_id_and_timestamp(client: TestClient) -> None:
    resp = client.post(
        f"/api/v1/agents/{_AGENT}/memory/events",
        headers=_auth(),
        json={"kind": "observation", "content": "user likes pgvector"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"].startswith("evt_")
    assert body["timestamp"]  # server-assigned ISO-8601


def test_append_memory_event_rejects_invalid_kind(client: TestClient) -> None:
    resp = client.post(
        f"/api/v1/agents/{_AGENT}/memory/events",
        headers=_auth(),
        json={"kind": "rumor", "content": "x"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_INPUT"


def test_append_memory_event_unknown_agent_returns_404(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/agents/agent-ghost/memory/events",
        headers=_auth(),
        json={"kind": "observation", "content": "x"},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "AGENT_NOT_FOUND"


# --------------------------- Memory events: GET list ---------------------------

def _seed_events(client: TestClient, count: int = 3) -> None:
    for i in range(count):
        client.post(
            f"/api/v1/agents/{_AGENT}/memory/events",
            headers=_auth(),
            json={
                "kind": "observation" if i % 2 == 0 else "tool_use",
                "content": f"event {i}",
            },
        )


def test_list_memory_events_returns_inserted_items(client: TestClient) -> None:
    _seed_events(client, count=3)
    resp = client.get(f"/api/v1/agents/{_AGENT}/memory/events", headers=_auth())
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [i["content"] for i in items] == ["event 0", "event 1", "event 2"]


def test_list_memory_events_filters_by_kind(client: TestClient) -> None:
    _seed_events(client, count=4)
    resp = client.get(
        f"/api/v1/agents/{_AGENT}/memory/events?kind=tool_use", headers=_auth()
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(i["kind"] == "tool_use" for i in items)


def test_list_memory_events_cursor_pagination(client: TestClient) -> None:
    _seed_events(client, count=5)
    page1 = client.get(
        f"/api/v1/agents/{_AGENT}/memory/events?limit=2", headers=_auth()
    ).json()
    assert page1["next_cursor"] is not None
    page2 = client.get(
        f"/api/v1/agents/{_AGENT}/memory/events?limit=2&cursor={page1['next_cursor']}",
        headers=_auth(),
    ).json()
    ids_seen = [i["id"] for i in page1["items"]] + [i["id"] for i in page2["items"]]
    assert len(ids_seen) == 4 and len(set(ids_seen)) == 4


# --------------------------- Memory search ---------------------------

def test_search_returns_substring_hits(client: TestClient) -> None:
    _seed_events(client, count=3)
    resp = client.post(
        f"/api/v1/agents/{_AGENT}/memory/search",
        headers=_auth(),
        json={"query": "event 1", "top_k": 5},
    )
    assert resp.status_code == 200
    hits = resp.json()["hits"]
    assert len(hits) == 1 and "event 1" in hits[0]["content"]


def test_search_top_k_out_of_range(client: TestClient) -> None:
    resp = client.post(
        f"/api/v1/agents/{_AGENT}/memory/search",
        headers=_auth(),
        json={"query": "x", "top_k": 999},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_INPUT"


def test_search_unknown_agent_returns_404(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/agents/agent-ghost/memory/search",
        headers=_auth(),
        json={"query": "x"},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "AGENT_NOT_FOUND"


# --------------------------- Memory flush ---------------------------

def test_flush_requires_exact_confirm_string(client: TestClient) -> None:
    resp = client.post(
        f"/api/v1/agents/{_AGENT}/memory/flush",
        headers=_auth(),
        json={"confirm": "yes please", "preserve_identity_and_soul": True},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_INPUT"


def test_flush_returns_deleted_count_and_preserves(client: TestClient) -> None:
    _seed_events(client, count=3)
    resp = client.post(
        f"/api/v1/agents/{_AGENT}/memory/flush",
        headers=_auth(),
        json={
            "confirm": "I understand this deletes all events for this agent.",
            "preserve_identity_and_soul": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["deleted_event_count"] == 3
    assert body["identity_preserved"] is True
    assert body["soul_preserved"] is True

    # Idempotent — second flush returns 0.
    again = client.post(
        f"/api/v1/agents/{_AGENT}/memory/flush",
        headers=_auth(),
        json={
            "confirm": "I understand this deletes all events for this agent.",
            "preserve_identity_and_soul": True,
        },
    ).json()
    assert again["deleted_event_count"] == 0


def test_flush_unknown_agent_returns_404(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/agents/agent-ghost/memory/flush",
        headers=_auth(),
        json={
            "confirm": "I understand this deletes all events for this agent.",
            "preserve_identity_and_soul": True,
        },
    )
    assert resp.status_code == 404


# --------------------------- OpenAPI completeness ---------------------------

def test_openapi_has_seven_documented_memory_endpoints(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    assert "/api/v1/agents/{agent_id}/identity" in paths
    assert {"get", "post"} <= paths["/api/v1/agents/{agent_id}/soul"].keys()
    assert "/api/v1/agents/{agent_id}/soul/history" in paths
    assert {"get", "post"} <= paths["/api/v1/agents/{agent_id}/memory/events"].keys()
    assert "/api/v1/agents/{agent_id}/memory/search" in paths
    assert "/api/v1/agents/{agent_id}/memory/flush" in paths
    assert "ErrorEnvelope" in spec["components"]["schemas"]
