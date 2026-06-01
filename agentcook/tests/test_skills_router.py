"""Skills router tests.

Day 27 landed the scaffolding (router file + schemas + invariant that
locked the router OUT of ``create_app``). Day 28 wires it in and bumps
the live spec to v1.1.0 — the freeze invariant flips here too.

These tests use an isolated FastAPI app for the GET/404/422 cases so we
don't drag in Memory router / auth / observability glue. The
spec-freeze invariant at the bottom uses the real ``create_app()`` to
verify the v1.1.0 wiring actually happened.
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

from agentcook_app.routers import skills  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    """Stand up an isolated FastAPI app with only the skills router."""
    app = FastAPI()
    app.include_router(skills.router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/v1/skills
# ---------------------------------------------------------------------------


class TestListSkills:
    def test_returns_200(self, client: TestClient):
        r = client.get("/api/v1/skills")
        assert r.status_code == 200

    def test_envelope_shape(self, client: TestClient):
        body = client.get("/api/v1/skills").json()
        assert set(body.keys()) == {"items", "total"}
        assert isinstance(body["items"], list)
        assert isinstance(body["total"], int)

    def test_total_matches_items(self, client: TestClient):
        body = client.get("/api/v1/skills").json()
        assert body["total"] == len(body["items"])

    def test_item_shape(self, client: TestClient):
        body = client.get("/api/v1/skills").json()
        first = body["items"][0]
        assert set(first.keys()) == {"id", "name", "description", "version", "category", "updated_at"}

    def test_five_mock_skills(self, client: TestClient):
        # Day 28 swaps to SkillRegistry; today the mock is fixed at 5.
        body = client.get("/api/v1/skills").json()
        assert body["total"] == 5

    def test_ids_are_kebab_case(self, client: TestClient):
        body = client.get("/api/v1/skills").json()
        for item in body["items"]:
            assert item["id"].replace("-", "").isalnum()
            assert item["id"] == item["id"].lower()


# ---------------------------------------------------------------------------
# GET /api/v1/skills/{id}
# ---------------------------------------------------------------------------


class TestGetSkill:
    def test_returns_known_skill(self, client: TestClient):
        r = client.get("/api/v1/skills/summarize-conversation")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == "summarize-conversation"

    def test_includes_body_field(self, client: TestClient):
        # Day 27 ships a placeholder body; Day 28 loads the real markdown.
        body = client.get("/api/v1/skills/summarize-conversation").json()
        assert "body" in body
        assert body["body"]  # non-empty string

    def test_unknown_skill_returns_404(self, client: TestClient):
        r = client.get("/api/v1/skills/does-not-exist")
        assert r.status_code == 404
        assert "not found" in r.json()["detail"].lower()

    def test_id_pattern_rejects_invalid_chars(self, client: TestClient):
        # Path pattern ``^[a-z0-9-]+$`` should 422 on uppercase / underscores.
        r = client.get("/api/v1/skills/HasUpper")
        assert r.status_code == 422

    def test_detail_extends_summary_shape(self, client: TestClient):
        """Detail response should be a superset of summary fields + body."""
        detail = client.get("/api/v1/skills/summarize-conversation").json()
        summary_fields = {"id", "name", "description", "version", "category", "updated_at"}
        assert summary_fields.issubset(set(detail.keys()))
        assert "body" in detail


# ---------------------------------------------------------------------------
# POST /api/v1/skills/{id}/test/stream — SSE
# ---------------------------------------------------------------------------


class TestSseStream:
    def test_returns_text_event_stream_content_type(self, client: TestClient):
        with client.stream(
            "POST",
            "/api/v1/skills/summarize-conversation/test/stream",
            json={"input": "hello"},
        ) as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")

    def test_emits_ten_chunks(self, client: TestClient):
        with client.stream(
            "POST",
            "/api/v1/skills/summarize-conversation/test/stream",
            json={"input": "hello"},
        ) as r:
            assert r.status_code == 200
            chunks = []
            for line in r.iter_lines():
                if line.startswith("data: "):
                    chunks.append(json.loads(line[6:]))
            assert len(chunks) == 10
            assert chunks[-1]["finished"] is True
            assert all(not c["finished"] for c in chunks[:-1])

    def test_chunk_carries_skill_id_and_input_echo(self, client: TestClient):
        with client.stream(
            "POST",
            "/api/v1/skills/classify-intent/test/stream",
            json={"input": "what is the weather"},
        ) as r:
            payloads = [
                json.loads(line[6:])
                for line in r.iter_lines()
                if line.startswith("data: ")
            ]
        first = payloads[0]
        assert "classify-intent" in first["delta"]
        assert "what is the weather" in first["delta"]

    def test_unknown_skill_returns_404(self, client: TestClient):
        r = client.post(
            "/api/v1/skills/does-not-exist/test/stream",
            json={"input": "hi"},
        )
        assert r.status_code == 404

    def test_invalid_skill_id_pattern_422(self, client: TestClient):
        r = client.post(
            "/api/v1/skills/HasUpper/test/stream",
            json={"input": "hi"},
        )
        assert r.status_code == 422

    def test_missing_input_field_422(self, client: TestClient):
        r = client.post(
            "/api/v1/skills/summarize-conversation/test/stream",
            json={},
        )
        assert r.status_code == 422

    def test_extra_fields_forbidden(self, client: TestClient):
        r = client.post(
            "/api/v1/skills/summarize-conversation/test/stream",
            json={"input": "hi", "rogue": "field"},
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Spec freeze invariant — Day 28: skills MUST be in create_app() at v1.1.0
# ---------------------------------------------------------------------------


class TestSpecFreezeBoundary:
    """Day 28 flipped this from 'router must be out' to 'router must be in'.

    Day 24: v1.0.0 frozen — no skills
    Day 27: scaffolding landed, router still NOT wired (Day 27 invariant)
    Day 28: wired + version bumped to 1.1.0 (this invariant)
    """

    def test_main_app_includes_skills_v1_1(self):
        from agentcook_app.main import create_app

        spec = create_app().openapi()
        paths = spec.get("paths", {})
        skills_paths = [p for p in paths if p.startswith("/api/v1/skills")]
        assert "/api/v1/skills" in skills_paths
        assert "/api/v1/skills/{skill_id}" in skills_paths
        assert "/api/v1/skills/{skill_id}/test/stream" in skills_paths

    def test_main_app_version_at_least_1_1_0(self):
        """Skills landed in v1.1.0 (Day 28). Subsequent minor bumps
        (delegations + logs in v1.2.0 on Day 31, etc.) advance the
        version forward — assert the floor, not a specific value, so
        future bumps don't have to chase this test.
        """
        from agentcook_app.main import create_app

        info = create_app().openapi()["info"]
        # Lex-sort works for our strict X.Y.Z scheme through 9.x.x.
        assert info["version"] >= "1.1.0"
        assert info["x-scope"] == "python-runtime"
