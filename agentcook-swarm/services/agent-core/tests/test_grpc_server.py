"""Unit tests for grpc_server module (mock-based, no real gRPC transport)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from grpc_server import ChatServiceServicer, _parse_sse_frame


class TestParseSSEFrame:
    def test_valid_data_line(self):
        line = 'data: {"role":"assistant","content":"hi","done":false}'
        result = _parse_sse_frame(line)
        assert result == {"role": "assistant", "content": "hi", "done": False}

    def test_terminal_frame_with_metadata(self):
        meta = {
            "model": "gpt-4o",
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "request_id": "abc",
        }
        line = (
            f'data: {{"role":"assistant","content":"","done":true,"metadata":{json.dumps(meta)}}}'
        )
        result = _parse_sse_frame(line)
        assert result["done"] is True
        assert result["metadata"]["model"] == "gpt-4o"

    def test_non_data_line_returns_none(self):
        assert _parse_sse_frame("event: message") is None
        assert _parse_sse_frame("") is None
        assert _parse_sse_frame(": comment") is None

    def test_invalid_json_returns_none(self):
        assert _parse_sse_frame("data: not json") is None

    def test_empty_data_returns_none(self):
        assert _parse_sse_frame("data: ") is None


class TestChatServiceServicer:
    def test_instantiation(self):
        servicer = ChatServiceServicer()
        assert servicer._request_count == 0


class _FakePb2:
    """Stand-in for the generated agentcook_pb2 module."""

    class ChatMetadata:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class ChatFrame:
        def __init__(self, **kw):
            self.__dict__.update(kw)


class _Context:
    def __init__(self, metadata=()):
        self._metadata = metadata
        self.aborted = None

    def invocation_metadata(self):
        return self._metadata

    async def abort(self, code, details):
        self.aborted = (code, details)


def _request(**kw):
    from types import SimpleNamespace

    base = dict(
        session_id="g-1",
        message="calculate 6 * 7",
        plugin_ids=[],
        model="",
        temperature=0.0,
        max_tokens=0,
    )
    base.update(kw)
    return SimpleNamespace(**base)


class TestStreamChatRunsTheAgentLoop:
    @pytest.fixture(autouse=True)
    def _pb2(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "agentcook_pb2", _FakePb2)
        grpc = pytest.importorskip("grpc")
        import grpc_server

        monkeypatch.setattr(grpc_server, "grpc", grpc, raising=False)

    def _container(self, **overrides):
        import dataclasses

        from agentcook_app.config import Settings
        from agentcook_app.container import AppContainer

        settings = dataclasses.replace(Settings.from_env({}), **overrides)
        return AppContainer(settings)

    async def test_streams_text_and_terminal_metadata(self):
        servicer = ChatServiceServicer(self._container())
        frames = [f async for f in servicer.StreamChat(_request(), _Context())]
        assert frames[-1].done is True
        assert frames[-1].metadata.model == "mock-agent"
        assert frames[-1].metadata.prompt_tokens > 0
        assert "42" in "".join(f.content for f in frames)

    async def test_required_auth_without_token_is_unauthenticated(self):
        import grpc

        servicer = ChatServiceServicer(self._container(auth_mode="required"))
        ctx = _Context()
        frames = [f async for f in servicer.StreamChat(_request(), ctx)]
        assert frames == []
        assert ctx.aborted[0] == grpc.StatusCode.UNAUTHENTICATED

    async def test_bad_token_is_unauthenticated(self):
        import grpc

        servicer = ChatServiceServicer(self._container())
        ctx = _Context(metadata=(("authorization", "Bearer not-a-jwt"),))
        frames = [f async for f in servicer.StreamChat(_request(), ctx)]
        assert frames == [] and ctx.aborted[0] == grpc.StatusCode.UNAUTHENTICATED

    async def test_invalid_model_maps_to_status(self):
        import grpc

        servicer = ChatServiceServicer(self._container())
        ctx = _Context()
        [f async for f in servicer.StreamChat(_request(model="nope:x"), ctx)]
        assert ctx.aborted[0] == grpc.StatusCode.UNAVAILABLE
