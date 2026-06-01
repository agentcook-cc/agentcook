"""Tests for the /api/v1/chat/stream SSE endpoint."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient

from agentcook_app.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    from starlette.testclient import TestClient
    return TestClient(app)


# ---------------------------------------------------------------------------
# Basic endpoint tests
# ---------------------------------------------------------------------------


class TestChatStreamEndpoint:
    def test_stream_returns_event_stream(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-1", "message": "hello"},
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    def test_stream_frames_are_valid_json(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-1", "message": "hello"},
        )
        assert resp.status_code == 200

        frames = []
        for line in resp.text.split("\n"):
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                frames.append(payload)

        assert len(frames) >= 2  # at least first + terminal
        # First frame echoes session_id
        assert frames[0]["session_id"] == "sess-1"
        assert frames[0]["done"] is False
        # Last frame is terminal
        assert frames[-1]["done"] is True

    def test_stream_terminal_frame_has_metadata(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-1", "message": "test"},
        )
        frames = [
            json.loads(line[6:])
            for line in resp.text.split("\n")
            if line.startswith("data: ")
        ]
        terminal = frames[-1]
        assert terminal["done"] is True
        assert "model" in terminal["metadata"]
        assert "usage" in terminal["metadata"]
        assert "request_id" in terminal["metadata"]

    def test_stream_content_frames_have_text(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-1", "message": "explain python"},
        )
        frames = [
            json.loads(line[6:])
            for line in resp.text.split("\n")
            if line.startswith("data: ")
        ]
        content_frames = [f for f in frames if f["content"] and not f["done"]]
        assert len(content_frames) >= 1
        # All content frames have role=assistant
        assert all(f["role"] == "assistant" for f in content_frames)

    def test_stream_with_plugins(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            json={
                "session_id": "sess-1",
                "message": "use my plugin",
                "plugin_ids": ["plugin-a", "plugin-b"],
            },
        )
        assert resp.status_code == 200
        frames = [
            json.loads(line[6:])
            for line in resp.text.split("\n")
            if line.startswith("data: ")
        ]
        # Plugin response should mention plugins/tools
        content = "".join(f["content"] for f in frames)
        assert "plugin" in content.lower() or "tool" in content.lower()

    def test_stream_with_model_override(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            json={
                "session_id": "sess-1",
                "message": "hello",
                "model": "claude-3-sonnet",
            },
        )
        assert resp.status_code == 200
        frames = [
            json.loads(line[6:])
            for line in resp.text.split("\n")
            if line.startswith("data: ")
        ]
        terminal = frames[-1]
        assert terminal["metadata"]["model"] == "claude-3-sonnet"


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestChatStreamValidation:
    def test_empty_session_id_rejected(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "   ", "message": "hello"},
        )
        assert resp.status_code == 400

    def test_missing_message_rejected(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-1"},
        )
        assert resp.status_code == 422

    def test_empty_message_rejected(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-1", "message": ""},
        )
        assert resp.status_code == 422

    def test_missing_session_id_rejected(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            json={"message": "hello"},
        )
        assert resp.status_code == 422

    def test_temperature_out_of_range(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "s1", "message": "hi", "temperature": 3.0},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Headers tests
# ---------------------------------------------------------------------------


class TestChatStreamHeaders:
    def test_cache_control_no_cache(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-1", "message": "hello"},
        )
        assert resp.headers.get("cache-control") == "no-cache"

    def test_x_accel_buffering_no(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-1", "message": "hello"},
        )
        assert resp.headers.get("x-accel-buffering") == "no"


# ---------------------------------------------------------------------------
# SSE format tests
# ---------------------------------------------------------------------------


class TestChatStreamSSEFormat:
    def test_frames_follow_sse_wire_format(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-1", "message": "hello"},
        )
        # Each frame should be "data: {...}\n\n"
        raw = resp.text
        # Split by double newline to get frames
        parts = raw.split("\n\n")
        data_parts = [p for p in parts if p.startswith("data: ")]
        assert len(data_parts) >= 2

    def test_all_frames_parseable_as_json(self, client):
        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-1", "message": "hello"},
        )
        for line in resp.text.split("\n"):
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                assert "role" in payload
                assert "done" in payload
