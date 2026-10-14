"""Live log stream: LogHub + /api/v1/logs/stream."""

from __future__ import annotations

import asyncio
import contextlib
import logging

import pytest
from agentcook_app.log_stream import LogHub, LogHubHandler, get_log_hub, structlog_processor
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


class TestLogHub:
    def test_ring_buffer_is_bounded(self) -> None:
        hub = LogHub(capacity=3)
        for i in range(5):
            hub.publish(hub.frame_from_event({"event": f"e{i}"}, logger_name="t"))
        assert [f["event"] for f in hub.recent()] == ["e2", "e3", "e4"]
        assert [f["event"] for f in hub.recent(2)] == ["e3", "e4"]

    def test_frame_shape_and_redaction(self) -> None:
        hub = LogHub()
        frame = hub.frame_from_event(
            {
                "event": "login",
                "level": "warn",
                "request_id": "abc",
                "api_key": "sk-123",
                "user": "u1",
                "obj": object(),
            },
            logger_name="auth",
        )
        assert frame["level"] == "warning"
        assert frame["logger"] == "auth"
        assert frame["request_id"] == "abc"
        assert frame["extra"]["api_key"] == "[redacted]"
        assert frame["extra"]["user"] == "u1"
        assert isinstance(frame["extra"]["obj"], str)

    def test_min_level_filter(self) -> None:
        hub = LogHub()
        for level in ("debug", "info", "error"):
            hub.publish(hub.frame_from_event({"event": level, "level": level}, logger_name=None))
        assert [f["event"] for f in hub.recent(min_level="info")] == ["info", "error"]

    async def test_subscribers_receive_new_frames(self) -> None:
        hub = LogHub()
        hub.bind_loop(asyncio.get_running_loop())
        received: list[str] = []

        async def consume() -> None:
            async with contextlib.aclosing(hub.subscribe()) as frames:
                async for frame in frames:
                    received.append(frame["event"])
                    if len(received) == 2:
                        return

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        assert hub.subscriber_count == 1
        hub.publish(hub.frame_from_event({"event": "a"}, logger_name=None))
        hub.publish(hub.frame_from_event({"event": "b"}, logger_name=None))
        await asyncio.wait_for(task, timeout=1)
        assert received == ["a", "b"]
        assert hub.subscriber_count == 0

    def test_stdlib_and_structlog_feed_the_global_hub(self) -> None:
        hub = get_log_hub()
        logging.getLogger("agentcook.test").addHandler(LogHubHandler())
        logging.getLogger("agentcook.test").warning("stdlib line %s", 42)
        structlog_processor(None, "info", {"event": "structlog line", "k": "v"})
        events = [f["event"] for f in hub.recent(10)]
        assert "stdlib line 42" in events and "structlog line" in events


class TestLogsEndpoint:
    def test_snapshot_returns_recent_frames_and_finishes(self, client: TestClient, sse) -> None:
        hub = get_log_hub()
        for i in range(5):
            hub.publish(hub.frame_from_event({"event": f"snap-{i}"}, logger_name="t"))
        frames = sse(client.get("/api/v1/logs/stream?limit=3").text)
        assert len(frames) == 3
        assert frames[-1]["extra"]["finished"] is True
        assert all(not f["extra"].get("finished") for f in frames[:-1])
        assert set(frames[0]) == {"timestamp", "level", "event", "request_id", "logger", "extra"}

    def test_level_filter(self, client: TestClient, sse) -> None:
        get_log_hub().publish(
            get_log_hub().frame_from_event({"event": "boom", "level": "error"}, logger_name="t")
        )
        frames = sse(client.get("/api/v1/logs/stream?limit=50&level=error").text)
        assert frames and all(f["level"] in ("error", "critical") for f in frames)

    @pytest.mark.parametrize("query", ["limit=0", "limit=501", "level=verbose", "history=-1"])
    def test_invalid_query_is_422(self, client: TestClient, query: str) -> None:
        assert client.get(f"/api/v1/logs/stream?{query}").status_code == 422

    def test_required_auth_mode_needs_admin(self, make_app, auth) -> None:
        with TestClient(make_app(auth_mode="required")) as client:
            assert client.get("/api/v1/logs/stream").status_code == 401
            assert client.get("/api/v1/logs/stream", headers=auth()).status_code == 403
            ok = client.get("/api/v1/logs/stream", headers=auth(scopes="admin"))
            assert ok.status_code == 200
