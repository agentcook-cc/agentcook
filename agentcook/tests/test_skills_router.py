"""Skills API — live registry (bundled skills + AGENTCOOK_SKILLS_DIRS)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit

BUNDLED = {
    "classify-intent",
    "competitor-analysis",
    "extract-entities",
    "generate-followups",
    "listing-optimizer",
    "summarize-conversation",
    "translate-text",
}


class TestListSkills:
    def test_lists_bundled_skills(self, client: TestClient) -> None:
        body = client.get("/api/v1/skills").json()
        assert {s["id"] for s in body["items"]} == BUNDLED
        assert body["total"] == len(BUNDLED)

    def test_summary_shape_matches_contract(self, client: TestClient) -> None:
        items = {s["id"]: s for s in client.get("/api/v1/skills").json()["items"]}
        assert items["summarize-conversation"] == {
            "id": "summarize-conversation",
            "name": "Summarize Conversation",
            "description": "Condense a long chat into key bullet points.",
            "version": "1.0.0",
            "category": "memory",
            "updated_at": "2026-06-03T09:00:00+00:00",
        }

    def test_sorted_by_category_then_id(self, client: TestClient) -> None:
        items = client.get("/api/v1/skills").json()["items"]
        keys = [(s["category"], s["id"]) for s in items]
        assert keys == sorted(keys)

    def test_extra_skill_dir_adds_and_overrides(self, make_app, tmp_path: Path) -> None:
        from agentcook_app.config import BUNDLED_SKILLS_DIR

        (tmp_path / "refunds.md").write_text(
            "---\nname: refund-policy\ndescription: Answer refund questions\n---\nBody",
            encoding="utf-8",
        )
        (tmp_path / "translate.md").write_text(
            "---\nname: translate-text\ndescription: Custom translator\n"
            "version: 9.0.0\n---\nCustom",
            encoding="utf-8",
        )
        app = make_app(skills_dirs=(BUNDLED_SKILLS_DIR, tmp_path))
        with TestClient(app) as client:
            items = {s["id"]: s for s in client.get("/api/v1/skills").json()["items"]}
            assert "refund-policy" in items
            assert items["refund-policy"]["category"] == "general"
            assert items["translate-text"]["version"] == "9.0.0"
            assert client.get("/api/v1/skills/translate-text").json()["body"] == "Custom"


class TestGetSkill:
    def test_returns_body(self, client: TestClient) -> None:
        body = client.get("/api/v1/skills/listing-optimizer").json()
        assert body["id"] == "listing-optimizer"
        assert body["body"].startswith("# Optimize a product listing")

    def test_unknown_skill_is_404_envelope(self, client: TestClient) -> None:
        resp = client.get("/api/v1/skills/nope")
        assert resp.status_code == 404
        assert resp.json()["code"] == "SKILL_NOT_FOUND"

    @pytest.mark.parametrize("bad", ["UPPER", "has_underscore", "-leading"])
    def test_invalid_id_is_422(self, client: TestClient, bad: str) -> None:
        assert client.get(f"/api/v1/skills/{bad}").status_code == 422


class TestSkillTestStream:
    def test_streams_frames_until_finished(self, client: TestClient, sse) -> None:
        resp = client.post(
            "/api/v1/skills/summarize-conversation/test/stream",
            json={"input": "What did I ask earlier?", "args": {"max_tokens": 256}},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        frames = sse(resp.text)
        assert [f["chunk_index"] for f in frames] == list(range(len(frames)))
        assert frames[-1]["finished"] is True and frames[-1]["type"] == "done"
        assert all(not f["finished"] for f in frames[:-1])
        assert "".join(f["delta"] for f in frames).strip()
        assert frames[-1]["metadata"]["skill"] == "summarize-conversation"

    def test_skill_test_can_use_tools(self, client: TestClient, sse) -> None:
        frames = sse(
            client.post(
                "/api/v1/skills/competitor-analysis/test/stream",
                json={"input": "calculate 49.99 - 29.99"},
            ).text
        )
        kinds = [f["type"] for f in frames]
        assert "tool_call" in kinds and "tool_result" in kinds

    def test_unknown_skill_is_404(self, client: TestClient) -> None:
        resp = client.post("/api/v1/skills/nope/test/stream", json={"input": "x"})
        assert resp.status_code == 404

    def test_missing_input_is_422(self, client: TestClient) -> None:
        resp = client.post("/api/v1/skills/translate-text/test/stream", json={})
        assert resp.status_code == 422
