"""Anthropic Claude provider tests.

Buffer Day 59 v1.1 — closes the Day 9-10 backlog. Anthropic SDK is
deliberately not assumed installed (``agentcook-providers[anthropic]``
is an optional extra), so every test injects a mock client built from
``SimpleNamespace`` + ``AsyncMock``. This mirrors the
``test_openai_provider_tracing.py`` pattern and lets the test suite
stay green even when the upstream API key is unavailable.

Coverage scope:

1. Default model + default context window
2. Model override + GLM-style context window fallback (unknown model)
3. ``from_env`` reads ``ANTHROPIC_API_KEY`` / ``ANTHROPIC_MODEL`` / raises when missing
4. Factory ``create_provider("anthropic")`` returns an AnthropicProvider
5. ``chat()`` mocks ``messages.create`` and verifies system-message split,
   stop_reason mapping, and ChatResponse shape
6. ``stream_chat()`` mocks ``messages.stream`` async context manager and
   verifies content_block_delta → ChatChunk conversion + terminal frame

Tools / tool-use are intentionally **not** tested in v1.1 — Phase 6 backlog.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit

from agentcook_core import Message  # noqa: E402
from agentcook_providers import AnthropicProvider, create_provider  # noqa: E402
from agentcook_providers.anthropic_provider import (  # noqa: E402
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_MAX_TOKENS,
    _split_system_messages,
    _stop_reason_to_finish,
)


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _fake_message(
    text: str = "Hello!",
    input_tokens: int = 10,
    output_tokens: int = 5,
    stop_reason: str = "end_turn",
):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        stop_reason=stop_reason,
    )


def _build_mock_provider(
    create_return: Any,
    model: str = DEFAULT_ANTHROPIC_MODEL,
) -> AnthropicProvider:
    mock_create = AsyncMock(return_value=create_return)
    mock_client = SimpleNamespace(
        messages=SimpleNamespace(create=mock_create)
    )
    return AnthropicProvider(model=model, client=mock_client)  # type: ignore[arg-type]


def _stub_anthropic_module(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Inject a fake `anthropic` module so __init__ doesn't ImportError
    when the SDK isn't installed in this venv. Returns a captured kwargs
    dict so callers can assert what AsyncAnthropic was constructed with."""
    captured: dict[str, Any] = {}

    class FakeAsyncAnthropic:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            captured.update(kwargs)
            self.messages = SimpleNamespace(create=AsyncMock(), stream=AsyncMock())

    import sys

    fake_module = SimpleNamespace(AsyncAnthropic=FakeAsyncAnthropic)
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)
    return captured


# ---------------------------------------------------------------------------
# 1. Default model + context window
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_default_model_is_sonnet_4_6(self):
        assert DEFAULT_ANTHROPIC_MODEL == "claude-sonnet-4-6"

    def test_default_max_tokens_is_4096(self):
        # Anthropic API requires max_tokens; OpenAI doesn't. Pin the default.
        assert DEFAULT_MAX_TOKENS == 4_096

    def test_known_model_context_window(self):
        provider = _build_mock_provider(_fake_message(), model="claude-sonnet-4-6")
        assert provider.context_window == 200_000

    def test_unknown_model_falls_back_to_default_window(self):
        provider = _build_mock_provider(_fake_message(), model="claude-99-future")
        assert provider.context_window == 200_000  # fallback default

    def test_count_tokens_uses_4_char_heuristic(self):
        provider = _build_mock_provider(_fake_message())
        assert provider.count_tokens("hello world") == 11 // 4
        assert provider.count_tokens("") == 1  # min 1


# ---------------------------------------------------------------------------
# 2. Helper unit tests (system split + stop_reason mapping)
# ---------------------------------------------------------------------------


class TestSystemSplit:
    def test_no_system_messages_returns_none(self):
        msgs = [Message(role="user", content="hi")]
        system, anth_msgs = _split_system_messages(msgs)
        assert system is None
        assert anth_msgs == [{"role": "user", "content": "hi"}]

    def test_single_system_message_extracted(self):
        msgs = [
            Message(role="system", content="be brief"),
            Message(role="user", content="hi"),
        ]
        system, anth_msgs = _split_system_messages(msgs)
        assert system == "be brief"
        assert anth_msgs == [{"role": "user", "content": "hi"}]

    def test_multiple_system_messages_concatenated(self):
        msgs = [
            Message(role="system", content="be brief"),
            Message(role="system", content="answer in english"),
            Message(role="user", content="hi"),
        ]
        system, anth_msgs = _split_system_messages(msgs)
        assert system == "be brief\n\nanswer in english"
        assert len(anth_msgs) == 1


class TestStopReasonMapping:
    @pytest.mark.parametrize(
        "stop_reason,expected",
        [
            ("end_turn", "stop"),
            ("stop_sequence", "stop"),
            ("max_tokens", "length"),
            ("tool_use", "tool_calls"),
        ],
    )
    def test_known_stop_reason(self, stop_reason: str, expected: str):
        assert _stop_reason_to_finish(stop_reason) == expected

    def test_none_returns_none(self):
        assert _stop_reason_to_finish(None) is None

    def test_unknown_returns_none(self):
        # Future stop_reason values shouldn't crash; map to None and let
        # the caller decide what to do.
        assert _stop_reason_to_finish("future_reason") is None


# ---------------------------------------------------------------------------
# 3. from_env classmethod
# ---------------------------------------------------------------------------


class TestFromEnv:
    def test_raises_when_api_key_missing(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is required"):
            AnthropicProvider.from_env()

    def test_reads_env_vars(self, monkeypatch: pytest.MonkeyPatch):
        captured = _stub_anthropic_module(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key-claude")
        monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-7")

        provider = AnthropicProvider.from_env()
        assert provider.model_name == "claude-opus-4-7"
        assert captured["api_key"] == "env-key-claude"


# ---------------------------------------------------------------------------
# 4. Factory dispatch
# ---------------------------------------------------------------------------


class TestFactoryDispatch:
    def test_create_provider_anthropic_returns_instance(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # Defend against env leaking across tests — earlier TestFromEnv
        # cases set ANTHROPIC_MODEL via monkeypatch and pytest does
        # restore at function exit, but this guard keeps the assertion
        # honest if the test is run in isolation under a polluted shell.
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
        _stub_anthropic_module(monkeypatch)
        provider = create_provider(provider="anthropic", api_key="test-key")
        assert isinstance(provider, AnthropicProvider)
        assert provider.model_name == DEFAULT_ANTHROPIC_MODEL

    def test_create_provider_anthropic_respects_explicit_model(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
        _stub_anthropic_module(monkeypatch)
        provider = create_provider(
            provider="anthropic", model="claude-3-5-haiku-20241022", api_key="test"
        )
        assert provider.model_name == "claude-3-5-haiku-20241022"

    def test_factory_anthropic_no_longer_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # Day 59 closure — Anthropic was the last NotImplementedError branch.
        monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
        _stub_anthropic_module(monkeypatch)
        monkeypatch.setenv("AGENTCOOK_LLM_PROVIDER", "anthropic")
        provider = create_provider(api_key="test")
        assert isinstance(provider, AnthropicProvider)


# ---------------------------------------------------------------------------
# 5. chat() — message split + ChatResponse shape
# ---------------------------------------------------------------------------


class TestChat:
    async def test_chat_basic_flow(self):
        provider = _build_mock_provider(_fake_message(text="你好"))
        response = await provider.chat([Message(role="user", content="hi")])
        assert response.message.content == "你好"
        assert response.usage.input == 10
        assert response.usage.output == 5
        assert response.finish_reason == "stop"

    async def test_chat_extracts_system_message(self):
        mock_create = AsyncMock(return_value=_fake_message())
        mock_client = SimpleNamespace(
            messages=SimpleNamespace(create=mock_create)
        )
        provider = AnthropicProvider(client=mock_client)  # type: ignore[arg-type]
        await provider.chat([
            Message(role="system", content="be brief"),
            Message(role="user", content="hi"),
        ])
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["system"] == "be brief"
        assert call_kwargs["messages"] == [{"role": "user", "content": "hi"}]

    async def test_chat_uses_default_max_tokens_when_unset(self):
        mock_create = AsyncMock(return_value=_fake_message())
        mock_client = SimpleNamespace(
            messages=SimpleNamespace(create=mock_create)
        )
        provider = AnthropicProvider(client=mock_client)  # type: ignore[arg-type]
        await provider.chat([Message(role="user", content="hi")])
        assert mock_create.call_args.kwargs["max_tokens"] == DEFAULT_MAX_TOKENS

    async def test_chat_passes_explicit_max_tokens_and_temperature(self):
        mock_create = AsyncMock(return_value=_fake_message())
        mock_client = SimpleNamespace(
            messages=SimpleNamespace(create=mock_create)
        )
        provider = AnthropicProvider(client=mock_client)  # type: ignore[arg-type]
        await provider.chat(
            [Message(role="user", content="hi")],
            temperature=0.7,
            max_tokens=512,
        )
        kw = mock_create.call_args.kwargs
        assert kw["max_tokens"] == 512
        assert kw["temperature"] == 0.7

    @pytest.mark.parametrize(
        "stop_reason,expected_finish",
        [
            ("end_turn", "stop"),
            ("max_tokens", "length"),
            ("tool_use", "tool_calls"),
            ("stop_sequence", "stop"),
        ],
    )
    async def test_chat_stop_reason_mapping(
        self, stop_reason: str, expected_finish: str
    ):
        provider = _build_mock_provider(
            _fake_message(stop_reason=stop_reason)
        )
        response = await provider.chat([Message(role="user", content="hi")])
        assert response.finish_reason == expected_finish


# ---------------------------------------------------------------------------
# 6. stream_chat() — async context manager + content_block_delta events
# ---------------------------------------------------------------------------


class _FakeStream:
    """Minimal async-context-manager + async iterator over events."""

    def __init__(self, events: list[Any]):
        self._events = events

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    def __aiter__(self):
        async def _gen():
            for e in self._events:
                yield e

        return _gen()


def _content_delta_event(text: str):
    return SimpleNamespace(
        type="content_block_delta",
        delta=SimpleNamespace(type="text_delta", text=text),
    )


def _message_delta_event(stop_reason: str):
    return SimpleNamespace(
        type="message_delta",
        delta=SimpleNamespace(stop_reason=stop_reason),
    )


class TestStreamChat:
    async def test_stream_chat_yields_text_deltas(self):
        stream = _FakeStream([
            _content_delta_event("你"),
            _content_delta_event("好"),
            _message_delta_event("end_turn"),
        ])
        mock_client = SimpleNamespace(
            messages=SimpleNamespace(stream=lambda **kw: stream)
        )
        provider = AnthropicProvider(client=mock_client)  # type: ignore[arg-type]

        chunks = [
            chunk async for chunk in provider.stream_chat(
                [Message(role="user", content="hi")]
            )
        ]
        # 2 content chunks + 1 terminal chunk with finish_reason
        assert len(chunks) == 3
        assert chunks[0].delta_content == "你"
        assert chunks[1].delta_content == "好"
        assert chunks[2].delta_content == ""
        assert chunks[2].finish_reason == "stop"

    async def test_stream_chat_handles_max_tokens_finish(self):
        stream = _FakeStream([
            _content_delta_event("partial"),
            _message_delta_event("max_tokens"),
        ])
        mock_client = SimpleNamespace(
            messages=SimpleNamespace(stream=lambda **kw: stream)
        )
        provider = AnthropicProvider(client=mock_client)  # type: ignore[arg-type]

        chunks = [
            chunk async for chunk in provider.stream_chat(
                [Message(role="user", content="long")]
            )
        ]
        assert chunks[-1].finish_reason == "length"

    async def test_stream_chat_skips_non_text_deltas(self):
        # Anthropic emits other event types (message_start / content_block_start /
        # ping). The provider should only surface text_delta to ChatChunk.
        stream = _FakeStream([
            SimpleNamespace(type="message_start", delta=None),
            SimpleNamespace(type="ping", delta=None),
            _content_delta_event("hi"),
            _message_delta_event("end_turn"),
        ])
        mock_client = SimpleNamespace(
            messages=SimpleNamespace(stream=lambda **kw: stream)
        )
        provider = AnthropicProvider(client=mock_client)  # type: ignore[arg-type]

        chunks = [
            chunk async for chunk in provider.stream_chat(
                [Message(role="user", content="hi")]
            )
        ]
        # Only "hi" content + terminal frame
        assert [c.delta_content for c in chunks] == ["hi", ""]
