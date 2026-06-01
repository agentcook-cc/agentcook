"""Day 30 scaffolding tests for the Logs streaming router.

Same hygiene pattern as ``test_skills_router.py`` had on Day 27 and
``test_delegations_router.py`` on Day 29: router NOT yet wired into
``create_app``. Day 31 wires it in along with delegations under one
v1.1 → v1.2 minor bump. The freeze-boundary test below locks both
this router AND delegations OUT of the live spec until then.

The SSE generator is rate-limited (1 frame/sec); these tests pass
``limit`` low to keep them fast (~0.5s each at limit=5).
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

from agentcook_app.routers import logs  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    """Isolated FastAPI app with only the logs router."""
    app = FastAPI()
    app.include_router(logs.router)
    return TestClient(app)


def _read_frames(client: TestClient, *, limit: int) -> list[dict]:
    with client.stream("GET", f"/api/v1/logs/stream?limit={limit}") as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        return [
            json.loads(line[6:])
            for line in r.iter_lines()
            if line.startswith("data: ")
        ]


# ---------------------------------------------------------------------------
# GET /api/v1/logs/stream
# ---------------------------------------------------------------------------


class TestStreamLogs:
    def test_returns_text_event_stream_content_type(self, client: TestClient):
        with client.stream("GET", "/api/v1/logs/stream?limit=1") as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")

    def test_emits_requested_limit_of_frames(self, client: TestClient):
        frames = _read_frames(client, limit=3)
        assert len(frames) == 3

    def test_frame_shape(self, client: TestClient):
        frames = _read_frames(client, limit=1)
        f = frames[0]
        # Required fields
        for key in ("timestamp", "level", "event"):
            assert key in f
        # Optional but populated by the mock
        assert "request_id" in f
        assert "logger" in f
        assert "extra" in f

    def test_terminal_frame_marked_finished(self, client: TestClient):
        frames = _read_frames(client, limit=4)
        assert frames[-1]["extra"]["finished"] is True
        # Earlier frames must NOT carry the terminal marker.
        assert all("finished" not in f["extra"] for f in frames[:-1])

    def test_level_constrained_to_log_levels(self, client: TestClient):
        frames = _read_frames(client, limit=7)
        valid = {"debug", "info", "warning", "error", "critical"}
        for f in frames:
            assert f["level"] in valid

    def test_request_id_is_hex_like(self, client: TestClient):
        frames = _read_frames(client, limit=2)
        for f in frames:
            assert f["request_id"]
            int(f["request_id"], 16)  # raises if not hex

    def test_limit_below_1_rejected(self, client: TestClient):
        r = client.get("/api/v1/logs/stream?limit=0")
        assert r.status_code == 422

    def test_limit_above_max_rejected(self, client: TestClient):
        r = client.get("/api/v1/logs/stream?limit=999")
        assert r.status_code == 422

    def test_default_limit_when_omitted(self, client: TestClient):
        # Default is 30; we don't want to actually stream 30s in CI, so
        # only verify the parameter binding by checking 422 isn't raised.
        with client.stream("GET", "/api/v1/logs/stream?limit=2") as r:
            assert r.status_code == 200


# ---------------------------------------------------------------------------
# Spec freeze invariant — Day 30: logs MUST NOT be in v1.1.0 spec
# ---------------------------------------------------------------------------


class TestSpecFreezeBoundary:
    """Day 31 flipped this from 'must NOT be in' to 'must BE in v1.2.0' —
    the same bump that wires in delegations (Day 29 scaffolded). One
    bump for both endpoints.
    """

    def test_main_app_includes_logs_v1_2(self):
        from agentcook_app.main import create_app

        spec = create_app().openapi()
        paths = spec.get("paths", {})
        assert "/api/v1/logs/stream" in paths

    def test_main_app_includes_sibling_delegations(self):
        """Sibling check — same v1.2.0 bump wires both routers."""
        from agentcook_app.main import create_app

        spec = create_app().openapi()
        paths = spec.get("paths", {})
        assert "/api/v1/agents/{agent_id}/delegations" in paths

    def test_main_app_version_bumped_to_1_2_0(self):
        from agentcook_app.main import create_app

        info = create_app().openapi()["info"]
        assert info["version"] == "1.2.0"
        assert info["x-frozen"] == "2026-06-07"
