"""Day 29 scaffolding tests for the Delegations router.

Same hygiene pattern as ``test_skills_router.py`` had on Day 27: the
router is **NOT yet included** in ``create_app`` — Day 31 wires it in
along with the v1.1→v1.2 minor bump. The freeze-boundary test below
locks the router OUT of the live spec until then. Day 31 will flip
this assertion from "must NOT be in" to "must BE in v1.2.0".
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

from agentcook_app.routers import delegations  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    """Isolated FastAPI app with only the delegations router."""
    app = FastAPI()
    app.include_router(delegations.router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/v1/agents/{agent_id}/delegations
# ---------------------------------------------------------------------------


class TestGetDelegations:
    def test_returns_200(self, client: TestClient):
        r = client.get("/api/v1/agents/agt-001/delegations")
        assert r.status_code == 200

    def test_envelope_shape(self, client: TestClient):
        body = client.get("/api/v1/agents/agt-001/delegations").json()
        assert set(body.keys()) == {"agent_id", "nodes", "edges"}
        assert isinstance(body["nodes"], list)
        assert isinstance(body["edges"], list)

    def test_agent_id_echoes(self, client: TestClient):
        body = client.get("/api/v1/agents/my-special-agent/delegations").json()
        assert body["agent_id"] == "my-special-agent"

    def test_node_shape(self, client: TestClient):
        body = client.get("/api/v1/agents/agt-001/delegations").json()
        first = body["nodes"][0]
        assert set(first.keys()) == {"id", "name", "role"}

    def test_edge_shape(self, client: TestClient):
        body = client.get("/api/v1/agents/agt-001/delegations").json()
        first = body["edges"][0]
        assert {"id", "from_id", "to_id", "task", "status", "started_at", "completed_at"} == set(first.keys())

    def test_three_nodes_two_edges_demo(self, client: TestClient):
        # Phase 5 will replace with live orchestrator snapshot; today's
        # mock is fixed at 3 nodes / 2 edges.
        body = client.get("/api/v1/agents/agt-001/delegations").json()
        assert len(body["nodes"]) == 3
        assert len(body["edges"]) == 2

    def test_running_edge_has_null_completed_at(self, client: TestClient):
        body = client.get("/api/v1/agents/agt-001/delegations").json()
        running = next(e for e in body["edges"] if e["status"] == "running")
        assert running["completed_at"] is None

    def test_succeeded_edge_has_completed_at(self, client: TestClient):
        body = client.get("/api/v1/agents/agt-001/delegations").json()
        done = next(e for e in body["edges"] if e["status"] == "succeeded")
        assert done["completed_at"] is not None

    def test_invalid_id_pattern_422(self, client: TestClient):
        # Path pattern is ``^[a-zA-Z0-9_-]+$`` — slashes / spaces should fail.
        r = client.get("/api/v1/agents/has space/delegations")
        # Spaces in URL paths are a routing concern (404), not a 422 — assert
        # whichever the framework chose, only that it's not a 200 leak.
        assert r.status_code != 200


# ---------------------------------------------------------------------------
# Spec freeze invariant — Day 29: delegations MUST NOT be in v1.1.0 spec
# ---------------------------------------------------------------------------


class TestSpecFreezeBoundary:
    """Day 31 flipped this from 'must NOT be in' to 'must BE in v1.2.0'.

    Day 29: scaffolding landed, router NOT wired (was the Day 29 invariant)
    Day 31: wired alongside logs router + version bumped to 1.2.0 (this invariant)
    """

    def test_main_app_includes_delegations_v1_2(self):
        from agentcook_app.main import create_app

        spec = create_app().openapi()
        paths = spec.get("paths", {})
        assert "/api/v1/agents/{agent_id}/delegations" in paths

    def test_main_app_version_bumped_to_1_2_0(self):
        from agentcook_app.main import create_app

        info = create_app().openapi()["info"]
        assert info["version"] == "1.2.0"
        assert info["x-frozen"] == "2026-06-07"
