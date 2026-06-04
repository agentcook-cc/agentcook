"""Phase 5 Day 49 — coverage for _stream_real_response SSE metadata fields.

Phase 4.6 (2026-06-01) introduced ``_stream_real_response`` in
``agentcook_app.routers.chat`` which calls a real LLM provider
(``agentcook_providers.create_provider().stream_chat()``) and wraps each
``ChatChunk`` into a ``ChatStreamFrame`` SSE frame. The terminal frame's
``metadata`` dict gained four new keys vs the mock path:

- ``source``: literal ``"provider"`` (vs mock path's ``"mock"``)
- ``provider``: class name of the provider singleton (e.g. ``"QwenProvider"``)
- ``output_chars``: total characters streamed (sum of ``delta_content`` len)
- ``finish_reason``: one of ``stop``/``length``/``tool_calls``/``content_filter``
  passed through from the terminal ``ChatChunk``

These fields drive observability (Langfuse hook + Grafana llm-metrics
dashboard) and downstream e2e assertions, so they need explicit unit
coverage that pins the contract without requiring a live LLM call.

Strategy: patch ``_get_provider`` to return a FakeProvider yielding
deterministic ``ChatChunk`` instances. Force ``AGENTCOOK_LLM_PROVIDER``
env so ``_use_mock()`` returns False and the endpoint routes to
``_stream_real_response``.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from starlette.testclient import TestClient

from agentcook_app.main import create_app
from agentcook_core.types import ChatChunk


class FakeQwenProvider:
    """Deterministic stand-in for agentcook_providers.QwenProvider.

    Emits ``chunks`` as a single sequence then a terminal chunk carrying
    ``terminal_finish_reason``. Configurable per-test via constructor.
    """

    def __init__(
        self,
        chunks: tuple[str, ...] = ("你好", "，", "世界"),
        terminal_finish_reason: str = "stop",
        model_name: str = "qwen-turbo",
    ) -> None:
        self._chunks = chunks
        self._terminal_finish_reason = terminal_finish_reason
        self.model_name = model_name

    async def stream_chat(
        self,
        messages: list[Any],
        **kwargs: Any,
    ) -> AsyncIterator[ChatChunk]:
        for delta in self._chunks:
            yield ChatChunk(delta_content=delta)
        yield ChatChunk(delta_content="", finish_reason=self._terminal_finish_reason)


@pytest.fixture
def real_path_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Client wired to the real (non-mock) chat path with a FakeQwenProvider."""
    monkeypatch.setenv("AGENTCOOK_LLM_PROVIDER", "qwen")
    monkeypatch.delenv("AGENTCOOK_CHAT_MOCK", raising=False)

    from agentcook_app.routers import chat as chat_module

    fake = FakeQwenProvider()
    monkeypatch.setattr(chat_module, "_get_provider", lambda: fake)
    monkeypatch.setattr(chat_module, "_provider_cache", fake, raising=False)

    return TestClient(create_app())


def _parse_frames(text: str) -> list[dict]:
    return [
        json.loads(line[6:])
        for line in text.split("\n")
        if line.startswith("data: ")
    ]


class TestRealResponseTerminalMetadata:
    """Pin the four metadata fields _stream_real_response emits on its
    terminal frame. Failure here means the SSE contract drifted and
    downstream consumers (Langfuse hook, Grafana llm-metrics dashboard,
    Playwright e2e) will break."""

    def test_source_is_provider(self, real_path_client: TestClient) -> None:
        resp = real_path_client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-real", "message": "hello"},
        )
        assert resp.status_code == 200
        frames = _parse_frames(resp.text)
        terminal = frames[-1]
        assert terminal["done"] is True
        assert terminal["metadata"]["source"] == "provider"

    def test_provider_class_name_present(self, real_path_client: TestClient) -> None:
        resp = real_path_client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-real", "message": "hello"},
        )
        terminal = _parse_frames(resp.text)[-1]
        assert terminal["metadata"]["provider"] == "FakeQwenProvider"

    def test_output_chars_matches_streamed_content(
        self, real_path_client: TestClient
    ) -> None:
        resp = real_path_client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-real", "message": "hello"},
        )
        frames = _parse_frames(resp.text)
        terminal = frames[-1]
        streamed = "".join(f["content"] for f in frames if not f["done"])
        assert terminal["metadata"]["output_chars"] == len(streamed)
        assert terminal["metadata"]["output_chars"] > 0

    def test_finish_reason_in_known_set(self, real_path_client: TestClient) -> None:
        resp = real_path_client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-real", "message": "hello"},
        )
        terminal = _parse_frames(resp.text)[-1]
        assert terminal["metadata"]["finish_reason"] in {
            "stop",
            "length",
            "tool_calls",
            "content_filter",
        }


class TestRealResponseTerminalMetadataParameterized:
    """Cover all four finish_reason values to ensure the contract holds
    regardless of why the upstream provider stopped streaming."""

    @pytest.mark.parametrize(
        "finish_reason",
        ["stop", "length", "tool_calls", "content_filter"],
    )
    def test_each_finish_reason_passes_through(
        self,
        monkeypatch: pytest.MonkeyPatch,
        finish_reason: str,
    ) -> None:
        monkeypatch.setenv("AGENTCOOK_LLM_PROVIDER", "qwen")
        monkeypatch.delenv("AGENTCOOK_CHAT_MOCK", raising=False)

        from agentcook_app.routers import chat as chat_module

        fake = FakeQwenProvider(terminal_finish_reason=finish_reason)
        monkeypatch.setattr(chat_module, "_get_provider", lambda: fake)
        monkeypatch.setattr(chat_module, "_provider_cache", fake, raising=False)

        client = TestClient(create_app())
        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-real", "message": "hi"},
        )
        terminal = _parse_frames(resp.text)[-1]
        assert terminal["metadata"]["finish_reason"] == finish_reason


class TestRealResponseFirstFrameContract:
    """The first frame still echoes session_id with done=False — same as
    the mock path. This anchors the wire format for B's ``useSseChat``."""

    def test_first_frame_echoes_session_id(
        self, real_path_client: TestClient
    ) -> None:
        resp = real_path_client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-real-first", "message": "ping"},
        )
        frames = _parse_frames(resp.text)
        assert frames[0]["session_id"] == "sess-real-first"
        assert frames[0]["done"] is False
        assert frames[0]["content"] == ""


class TestRealResponseErrorFrame:
    """When the provider raises mid-stream, the contract emits a terminal
    frame with ``error`` set + ``source="provider"`` so the frontend can
    surface the failure without breaking the SSE wire format."""

    def test_provider_exception_yields_error_frame(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AGENTCOOK_LLM_PROVIDER", "qwen")
        monkeypatch.delenv("AGENTCOOK_CHAT_MOCK", raising=False)

        class ExplodingProvider:
            model_name = "qwen-turbo"

            async def stream_chat(
                self, messages: list[Any], **kwargs: Any
            ) -> AsyncIterator[ChatChunk]:
                yield ChatChunk(delta_content="partial ")
                raise RuntimeError("upstream 429 rate limited")

        from agentcook_app.routers import chat as chat_module

        provider = ExplodingProvider()
        monkeypatch.setattr(chat_module, "_get_provider", lambda: provider)
        monkeypatch.setattr(chat_module, "_provider_cache", provider, raising=False)

        client = TestClient(create_app())
        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-err", "message": "boom"},
        )
        assert resp.status_code == 200
        terminal = _parse_frames(resp.text)[-1]
        assert terminal["done"] is True
        assert terminal["error"] is not None
        assert "RuntimeError" in terminal["error"]
        assert "rate limited" in terminal["error"]


class TestRealResponseProviderInitError:
    """Provider construction failure (e.g. missing ``openai`` extras causing
    ``ImportError``) must surface as a structured error frame, not a 0-byte
    SSE stream. Before the W3 fix ``_get_provider()`` ran outside the try
    block, so init errors propagated to starlette and closed the response
    after headers — useSseChat then showed "No response received" with no
    diagnostic signal."""

    def test_provider_init_error_returns_error_frame(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AGENTCOOK_LLM_PROVIDER", "qwen")
        monkeypatch.delenv("AGENTCOOK_CHAT_MOCK", raising=False)

        from agentcook_app.routers import chat as chat_module

        def _raising_get_provider() -> Any:
            raise ImportError("Install agentcook-providers[openai] to use OpenAIProvider.")

        monkeypatch.setattr(chat_module, "_provider_cache", None, raising=False)
        monkeypatch.setattr(chat_module, "_get_provider", _raising_get_provider)

        client = TestClient(create_app())
        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-init-err", "message": "hi"},
        )

        assert resp.status_code == 200
        frames = _parse_frames(resp.text)

        # First frame still goes out so useSseChat sees session_id.
        assert frames[0]["session_id"] == "sess-init-err"
        assert frames[0]["done"] is False

        # Terminal frame carries the ImportError text instead of empty stream.
        terminal = frames[-1]
        assert terminal["done"] is True
        assert terminal["error"] is not None
        assert "ImportError" in terminal["error"]
        assert "openai" in terminal["error"]
        assert terminal["metadata"]["source"] == "provider"

    def test_provider_override_init_error_returns_error_frame(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Same contract for the ADR-018 quota-resolver provider_override
        path — a failing ``create_provider(name)`` must not break the SSE
        stream either."""
        monkeypatch.setenv("AGENTCOOK_LLM_PROVIDER", "qwen")
        monkeypatch.delenv("AGENTCOOK_CHAT_MOCK", raising=False)

        from agentcook_app.routers import chat as chat_module

        async def _override_stream(request: Any) -> AsyncIterator[bytes]:
            async for frame in chat_module._stream_real_response(
                request, provider_override="nonexistent-provider"
            ):
                yield frame

        from agentcook_app.schemas_chat import ChatStreamRequest

        async def _collect() -> list[dict]:
            req = ChatStreamRequest(session_id="sess-override-err", message="hi")
            chunks = []
            async for frame_bytes in chat_module._stream_real_response(
                req, provider_override="nonexistent-provider"
            ):
                line = frame_bytes.decode().strip()
                if line.startswith("data: "):
                    chunks.append(json.loads(line[6:]))
            return chunks

        import asyncio

        frames = asyncio.run(_collect())
        terminal = frames[-1]
        assert terminal["done"] is True
        assert terminal["error"] is not None
        assert terminal["metadata"]["source"] == "provider"
        assert terminal["metadata"]["source"] == "provider"
