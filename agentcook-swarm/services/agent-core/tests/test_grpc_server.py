"""Unit tests for grpc_server module (mock-based, no real gRPC transport)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from grpc_server import ChatServiceServicer, _parse_sse_frame


class TestParseSSEFrame:
    def test_valid_data_line(self):
        line = 'data: {"role":"assistant","content":"hi","done":false}'
        result = _parse_sse_frame(line)
        assert result == {"role": "assistant", "content": "hi", "done": False}

    def test_terminal_frame_with_metadata(self):
        meta = {"model": "gpt-4o", "usage": {"input_tokens": 10, "output_tokens": 5}, "request_id": "abc"}
        line = f'data: {{"role":"assistant","content":"","done":true,"metadata":{json.dumps(meta)}}}'
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
