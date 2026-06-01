"""Verify OpenAIProvider emits the expected spans via agentcook_core.tracing.

Day 26 Phase 3 backlog (per Day 25 GAP analysis): the previous
instrumentation skipped the actual chat call because OpenAIProvider
didn't call ``get_tracer()``. After the Day 26 patch every chat /
stream_chat opens a span carrying ``agentcook.model.name`` /
``agentcook.model.provider`` / ``agentcook.tokens.in`` /
``agentcook.tokens.out`` so the LLM-call layer is finally visible in
Jaeger / Langfuse.

These tests use the same NoOp-by-default pattern from ``test_tracing.py``:
inject a recording tracer, run the provider, assert what it emitted.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit

from agentcook_core import Message  # noqa: E402
from agentcook_core.tracing import (  # noqa: E402
    Span,
    Tracer,
    reset_tracer,
    set_tracer,
)
from agentcook_providers import OpenAIProvider  # noqa: E402

# ---------------------------------------------------------------------------
# Recording fakes (same shape as test_tracing.py's; inlined to avoid import
# from another package's tests/ directory).
# ---------------------------------------------------------------------------


class RecordingSpan:
    def __init__(self, name: str, attributes: dict | None = None) -> None:
        self.name = name
        self.attributes: dict = dict(attributes or {})
        self.exceptions: list[BaseException] = []
        self.exited = False

    def __enter__(self) -> RecordingSpan:
        return self

    def __exit__(self, *args: Any) -> None:
        self.exited = True

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def record_exception(self, exc: BaseException) -> None:
        self.exceptions.append(exc)


class RecordingTracer:
    def __init__(self) -> None:
        self.spans: list[RecordingSpan] = []

    def start_span(self, name: str, *, attributes: dict | None = None) -> RecordingSpan:
        s = RecordingSpan(name, attributes)
        self.spans.append(s)
        return s


@pytest.fixture
def rec() -> RecordingTracer:
    reset_tracer()
    tracer = RecordingTracer()
    set_tracer(tracer)
    yield tracer
    reset_tracer()


# ---------------------------------------------------------------------------
# Mock helpers reused from test_providers.py shape
# ---------------------------------------------------------------------------


def _fake_completion(prompt_tokens: int = 12, completion_tokens: int = 3, finish: str = "stop"):
    msg = SimpleNamespace(content="hi", tool_calls=None)
    choice = SimpleNamespace(message=msg, finish_reason=finish)
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )
    return SimpleNamespace(choices=[choice], usage=usage)


def _build_mock_provider(create_return: Any, model: str = "gpt-4o-mini") -> OpenAIProvider:
    mock_create = AsyncMock(return_value=create_return)
    mock_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=mock_create))
    )
    return OpenAIProvider(model=model, client=mock_client)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Protocol Conformance
# ---------------------------------------------------------------------------


class TestRecordingFakeConformance:
    def test_recording_tracer_satisfies_protocol(self):
        assert isinstance(RecordingTracer(), Tracer)

    def test_recording_span_satisfies_protocol(self):
        assert isinstance(RecordingSpan("x"), Span)


# ---------------------------------------------------------------------------
# chat() — span emission
# ---------------------------------------------------------------------------


class TestChatSpan:
    async def test_emits_named_span(self, rec: RecordingTracer):
        provider = _build_mock_provider(_fake_completion())
        await provider.chat([Message(role="user", content="ping")])
        names = [s.name for s in rec.spans]
        assert "model.openai.chat" in names

    async def test_records_model_name_and_provider(self, rec: RecordingTracer):
        provider = _build_mock_provider(_fake_completion(), model="gpt-4o")
        await provider.chat([Message(role="user", content="x")])
        span = next(s for s in rec.spans if s.name == "model.openai.chat")
        assert span.attributes["agentcook.model.name"] == "gpt-4o"
        assert span.attributes["agentcook.model.provider"] == "openai"

    async def test_records_token_usage(self, rec: RecordingTracer):
        provider = _build_mock_provider(_fake_completion(prompt_tokens=42, completion_tokens=7))
        await provider.chat([Message(role="user", content="x")])
        span = next(s for s in rec.spans if s.name == "model.openai.chat")
        assert span.attributes["agentcook.tokens.in"] == 42
        assert span.attributes["agentcook.tokens.out"] == 7
        assert span.attributes["agentcook.tokens.total"] == 49

    async def test_records_finish_reason_when_present(self, rec: RecordingTracer):
        provider = _build_mock_provider(_fake_completion(finish="length"))
        await provider.chat([Message(role="user", content="x")])
        span = next(s for s in rec.spans if s.name == "model.openai.chat")
        assert span.attributes.get("agentcook.finish_reason") == "length"

    async def test_records_message_count_and_no_tools(self, rec: RecordingTracer):
        provider = _build_mock_provider(_fake_completion())
        await provider.chat([
            Message(role="system", content="be brief"),
            Message(role="user", content="x"),
        ])
        span = next(s for s in rec.spans if s.name == "model.openai.chat")
        assert span.attributes["agentcook.messages.count"] == 2
        assert span.attributes["agentcook.tools.count"] == 0

    async def test_span_exit_on_normal_path(self, rec: RecordingTracer):
        provider = _build_mock_provider(_fake_completion())
        await provider.chat([Message(role="user", content="x")])
        span = next(s for s in rec.spans if s.name == "model.openai.chat")
        assert span.exited is True


# ---------------------------------------------------------------------------
# stream_chat() — span emission
# ---------------------------------------------------------------------------


def _async_iter(items):
    """Helper: turn a list into an async iterator the mock client can return."""

    async def _gen():
        for item in items:
            yield item

    return _gen()


def _stream_chunk(content: str = "", finish_reason: str | None = None):
    delta = SimpleNamespace(content=content, tool_calls=None)
    choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


class TestStreamChatSpan:
    async def test_emits_stream_span(self, rec: RecordingTracer):
        chunks = [_stream_chunk("he"), _stream_chunk("llo"), _stream_chunk("", finish_reason="stop")]
        mock_create = AsyncMock(return_value=_async_iter(chunks))
        mock_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=mock_create))
        )
        provider = OpenAIProvider(model="gpt-4o-mini", client=mock_client)  # type: ignore[arg-type]

        out = [c async for c in provider.stream_chat([Message(role="user", content="x")])]
        assert len(out) == 3

        span = next(s for s in rec.spans if s.name == "model.openai.stream_chat")
        assert span.attributes["agentcook.model.name"] == "gpt-4o-mini"
        assert span.attributes["agentcook.stream"] is True
        assert span.attributes["agentcook.stream.chunks"] == 3
        assert span.exited is True

    async def test_records_finish_reason_from_terminal_chunk(self, rec: RecordingTracer):
        chunks = [_stream_chunk("ok"), _stream_chunk("", finish_reason="stop")]
        mock_create = AsyncMock(return_value=_async_iter(chunks))
        mock_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=mock_create))
        )
        provider = OpenAIProvider(model="gpt-4o-mini", client=mock_client)  # type: ignore[arg-type]
        async for _ in provider.stream_chat([Message(role="user", content="x")]):
            pass
        span = next(s for s in rec.spans if s.name == "model.openai.stream_chat")
        assert span.attributes.get("agentcook.finish_reason") == "stop"

    async def test_span_closed_on_early_consumer_break(self, rec: RecordingTracer):
        chunks = [_stream_chunk("a"), _stream_chunk("b"), _stream_chunk("c", finish_reason="stop")]
        mock_create = AsyncMock(return_value=_async_iter(chunks))
        mock_client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=mock_create))
        )
        provider = OpenAIProvider(model="gpt-4o-mini", client=mock_client)  # type: ignore[arg-type]

        gen = provider.stream_chat([Message(role="user", content="x")])
        # Consume one chunk then close — exercises the finally path.
        async for _ in gen:
            break
        await gen.aclose()

        span = next(s for s in rec.spans if s.name == "model.openai.stream_chat")
        assert span.exited is True
        # We don't assert chunks count here — depends on iterator timing —
        # only that the span was properly ended on early termination.
