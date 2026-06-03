"""Unit tests for ``agentcook_providers``.

No live network. ``OpenAIProvider`` is exercised against an
``AsyncMock`` standing in for ``AsyncOpenAI`` — the mock returns the
exact attribute shape the SDK does.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit

from agentcook_core import (  # noqa: E402
    ChatChunk,
    ChatResponse,
    LLMProviderProtocol,
    Message,
    ToolCall,
)
from agentcook_providers import (  # noqa: E402
    EchoProvider,
    FallbackProvider,
    OpenAIProvider,
    create_provider,
)

# --------------------------- EchoProvider ---------------------------

def test_echo_provider_satisfies_llm_provider_protocol() -> None:
    assert isinstance(EchoProvider(), LLMProviderProtocol)


async def test_echo_provider_chat_echoes_last_user_message() -> None:
    provider = EchoProvider(prefix="Demo")
    response = await provider.chat([
        Message(role="system", content="be helpful"),
        Message(role="user", content="hi"),
        Message(role="assistant", content="how can I help?"),
        Message(role="user", content="ping"),
    ])
    assert isinstance(response, ChatResponse)
    assert response.message.content == "[Demo] ping"
    assert response.finish_reason == "stop"
    assert response.usage.total > 0


async def test_echo_provider_stream_yields_per_char_then_finish() -> None:
    provider = EchoProvider(prefix="Demo")
    chunks = [c async for c in provider.stream_chat([Message(role="user", content="ab")])]
    assert "".join(c.delta_content for c in chunks) == "[Demo] ab"
    assert chunks[-1].finish_reason == "stop"


# --------------------------- OpenAIProvider ---------------------------

def _fake_chat_completion(content: str = "hi", tool_calls=None, finish_reason: str = "stop"):
    """Build the SimpleNamespace shape the SDK returns from ``create``."""
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=msg, finish_reason=finish_reason)
    usage = SimpleNamespace(prompt_tokens=12, completion_tokens=3, total_tokens=15)
    return SimpleNamespace(choices=[choice], usage=usage)


async def test_openai_provider_chat_round_trips_through_mock_client() -> None:
    fake_completion = _fake_chat_completion(content="pong")
    mock_create = AsyncMock(return_value=fake_completion)
    mock_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=mock_create)))

    provider = OpenAIProvider(model="gpt-4o-mini", client=mock_client)  # type: ignore[arg-type]
    response = await provider.chat([Message(role="user", content="ping")], temperature=0.2)

    assert response.message.content == "pong"
    assert response.usage.input == 12 and response.usage.output == 3
    assert response.finish_reason == "stop"

    sent = mock_create.await_args.kwargs
    assert sent["model"] == "gpt-4o-mini"
    assert sent["temperature"] == 0.2
    assert sent["messages"][0]["role"] == "user"


async def test_openai_provider_chat_decodes_tool_calls() -> None:
    """A tool_calls reply round-trips JSON arguments back to a dict."""
    raw_tc = SimpleNamespace(
        id="call_42",
        function=SimpleNamespace(name="search", arguments='{"q": "agentcook"}'),
    )
    mock_create = AsyncMock(
        return_value=_fake_chat_completion(content=None, tool_calls=[raw_tc], finish_reason="tool_calls")
    )
    mock_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=mock_create)))

    provider = OpenAIProvider(model="gpt-4o-mini", client=mock_client)  # type: ignore[arg-type]
    response = await provider.chat([Message(role="user", content="search agentcook")])

    assert response.message.content == ""
    assert response.message.tool_calls is not None
    tc = response.message.tool_calls[0]
    assert tc == ToolCall(id="call_42", name="search", arguments={"q": "agentcook"})
    assert response.finish_reason == "tool_calls"


async def test_openai_provider_serializes_tool_reply_correctly() -> None:
    """role=tool messages must map to OpenAI tool_call_id payload."""
    mock_create = AsyncMock(return_value=_fake_chat_completion(content="ok"))
    mock_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=mock_create)))

    provider = OpenAIProvider(model="gpt-4o-mini", client=mock_client)  # type: ignore[arg-type]
    await provider.chat([
        Message(role="user", content="search agentcook"),
        Message(
            role="assistant",
            content="",
            tool_calls=(ToolCall(id="call_42", name="search", arguments={"q": "agentcook"}),),
        ),
        Message(role="tool", content='{"hits": 3}', name="search", tool_call_id="call_42"),
    ])

    sent_messages = mock_create.await_args.kwargs["messages"]
    assistant_msg = sent_messages[1]
    assert assistant_msg["content"] is None  # OpenAI requires null when tool_calls set
    assert assistant_msg["tool_calls"][0]["function"]["name"] == "search"
    tool_msg = sent_messages[2]
    assert tool_msg["tool_call_id"] == "call_42"
    assert tool_msg["role"] == "tool"


# --------------------------- FallbackProvider ---------------------------

class _FailingProvider(EchoProvider):
    """Provider that raises a controllable exception on every ``chat``."""

    def __init__(self, exc: Exception, *, model: str = "failing-v0") -> None:
        super().__init__(model=model)
        self._exc = exc

    async def chat(self, messages, *, tools=None, temperature=None, max_tokens=None):  # type: ignore[override]
        raise self._exc

    async def stream_chat(  # type: ignore[override]
        self, messages, *, tools=None, temperature=None, max_tokens=None,
    ) -> AsyncIterator[ChatChunk]:
        raise self._exc
        yield  # pragma: no cover — make this an async generator


class _RateLimitError(Exception):
    status_code = 429


async def test_fallback_provider_falls_through_on_retryable_status() -> None:
    primary = _FailingProvider(_RateLimitError("rate limit hit"))
    backup = EchoProvider(prefix="Backup")
    chain = FallbackProvider([primary, backup])

    response = await chain.chat([Message(role="user", content="hi")])
    assert response.message.content == "[Backup] hi"


async def test_fallback_provider_reraises_on_non_retryable() -> None:
    primary = _FailingProvider(ValueError("logic bug"))
    backup = EchoProvider(prefix="Backup")
    chain = FallbackProvider([primary, backup])

    with pytest.raises(ValueError, match="logic bug"):
        await chain.chat([Message(role="user", content="hi")])


async def test_fallback_provider_keyword_match() -> None:
    """An exception with no status_code but 'overloaded' text is retryable."""
    primary = _FailingProvider(RuntimeError("provider is overloaded, try again later"))
    backup = EchoProvider(prefix="Backup")
    chain = FallbackProvider([primary, backup])
    response = await chain.chat([Message(role="user", content="hi")])
    assert response.message.content == "[Backup] hi"


# --------------------------- factory ---------------------------

def test_factory_creates_echo_provider() -> None:
    p = create_provider("echo")
    assert isinstance(p, EchoProvider)


# Zhipu adapter landed on Phase 5 Day 54 (Agent A) — see
# agentcook-providers/tests/test_zhipu_provider.py for the live coverage.
# Anthropic adapter landed on Buffer Day 59 (Agent A) — see
# agentcook-providers/tests/test_anthropic_provider.py for the live coverage.
# Both old "not implemented yet" expectations no longer apply; create_provider
# now returns the corresponding provider instance for both.


def test_factory_unknown_provider_raises() -> None:
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_provider("gemini")


def test_factory_no_provider_configured_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTCOOK_LLM_PROVIDER", raising=False)
    with pytest.raises(ValueError, match="No LLM provider configured"):
        create_provider()
