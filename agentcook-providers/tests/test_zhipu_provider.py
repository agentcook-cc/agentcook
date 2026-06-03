"""Zhipu (智谱) provider tests.

ZhipuProvider is a thin subclass of OpenAIProvider pinning the Zhipu
OpenAI-compatible base URL + GLM context-window table. The
inherited chat / stream_chat behaviour is covered by
test_openai_provider_tracing.py; this file focuses on what
ZhipuProvider adds:

1. Default base URL is the Zhipu endpoint
2. GLM context windows resolve correctly
3. ``from_env`` reads ZHIPU_API_KEY / ZHIPU_MODEL / ZHIPU_BASE_URL
4. Factory ``create_provider("zhipu")`` returns a ZhipuProvider
5. Sanity check that inherited chat() still works (one mock-client call)
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

pytestmark = pytest.mark.unit

from agentcook_core import Message  # noqa: E402
from agentcook_providers import ZhipuProvider, create_provider  # noqa: E402
from agentcook_providers.zhipu_provider import (  # noqa: E402
    DEFAULT_ZHIPU_MODEL,
    ZHIPU_BASE_URL,
)


# ---------------------------------------------------------------------------
# Mock helpers (same shape as test_openai_provider_tracing.py)
# ---------------------------------------------------------------------------


def _fake_completion(
    prompt_tokens: int = 10, completion_tokens: int = 5, finish: str = "stop"
):
    msg = SimpleNamespace(content="你好", tool_calls=None)
    choice = SimpleNamespace(message=msg, finish_reason=finish)
    usage = SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )
    return SimpleNamespace(choices=[choice], usage=usage)


def _build_mock_provider(
    create_return: Any, model: str = DEFAULT_ZHIPU_MODEL
) -> ZhipuProvider:
    mock_create = AsyncMock(return_value=create_return)
    mock_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=mock_create))
    )
    return ZhipuProvider(model=model, client=mock_client)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 1. Default base URL is the Zhipu endpoint (vs OpenAI default)
# ---------------------------------------------------------------------------


class TestDefaultBaseUrl:
    def test_default_base_url_is_zhipu(self, monkeypatch: pytest.MonkeyPatch):
        # Stub the openai SDK so __init__ doesn't blow up when openai isn't installed
        # in this test environment; capture what base_url was passed.
        captured: dict[str, Any] = {}

        class FakeAsyncOpenAI:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                captured.update(kwargs)
                self.chat = SimpleNamespace(
                    completions=SimpleNamespace(create=AsyncMock())
                )

        import agentcook_providers.openai_provider as openai_mod

        monkeypatch.setattr(openai_mod, "AsyncOpenAI", FakeAsyncOpenAI, raising=False)
        # Also stub `from openai import AsyncOpenAI` via sys.modules
        import sys

        fake_module = SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI)
        monkeypatch.setitem(sys.modules, "openai", fake_module)

        ZhipuProvider(model="glm-4-flash", api_key="test-key")
        assert captured["base_url"] == ZHIPU_BASE_URL

    def test_explicit_base_url_overrides_default(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        captured: dict[str, Any] = {}

        class FakeAsyncOpenAI:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                captured.update(kwargs)
                self.chat = SimpleNamespace(
                    completions=SimpleNamespace(create=AsyncMock())
                )

        import sys

        fake_module = SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI)
        monkeypatch.setitem(sys.modules, "openai", fake_module)

        ZhipuProvider(
            model="glm-4-flash",
            api_key="test-key",
            base_url="https://private.zhipu.example.com/v1",
        )
        assert captured["base_url"] == "https://private.zhipu.example.com/v1"


# ---------------------------------------------------------------------------
# 2. GLM context windows
# ---------------------------------------------------------------------------


class TestContextWindow:
    def test_glm_4_flash_window(self):
        provider = _build_mock_provider(_fake_completion(), model="glm-4-flash")
        assert provider.context_window == 128_000

    def test_glm_4_long_window(self):
        provider = _build_mock_provider(_fake_completion(), model="glm-4-long")
        assert provider.context_window == 1_000_000

    def test_unknown_glm_model_falls_back_to_openai_default(self):
        provider = _build_mock_provider(_fake_completion(), model="glm-99-future")
        # Falls back to OpenAIProvider.context_window's DEFAULT (128_000)
        assert provider.context_window == 128_000


# ---------------------------------------------------------------------------
# 3. from_env() classmethod
# ---------------------------------------------------------------------------


class TestFromEnv:
    def test_raises_when_api_key_missing(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("ZHIPU_API_KEY", raising=False)
        with pytest.raises(ValueError, match="ZHIPU_API_KEY is required"):
            ZhipuProvider.from_env()

    def test_reads_env_vars(self, monkeypatch: pytest.MonkeyPatch):
        captured: dict[str, Any] = {}

        class FakeAsyncOpenAI:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                captured.update(kwargs)
                self.chat = SimpleNamespace(
                    completions=SimpleNamespace(create=AsyncMock())
                )

        import sys

        fake_module = SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI)
        monkeypatch.setitem(sys.modules, "openai", fake_module)

        monkeypatch.setenv("ZHIPU_API_KEY", "env-key-abc")
        monkeypatch.setenv("ZHIPU_MODEL", "glm-4-plus")
        monkeypatch.delenv("ZHIPU_BASE_URL", raising=False)

        provider = ZhipuProvider.from_env()
        assert provider.model_name == "glm-4-plus"
        assert captured["api_key"] == "env-key-abc"
        assert captured["base_url"] == ZHIPU_BASE_URL


# ---------------------------------------------------------------------------
# 4. Factory dispatch
# ---------------------------------------------------------------------------


class TestFactoryDispatch:
    def test_create_provider_zhipu_returns_zhipu_instance(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        class FakeAsyncOpenAI:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.chat = SimpleNamespace(
                    completions=SimpleNamespace(create=AsyncMock())
                )

        import sys

        fake_module = SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI)
        monkeypatch.setitem(sys.modules, "openai", fake_module)

        provider = create_provider(provider="zhipu", api_key="test")
        assert isinstance(provider, ZhipuProvider)
        assert provider.model_name == DEFAULT_ZHIPU_MODEL

    def test_create_provider_zhipu_respects_explicit_model(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        class FakeAsyncOpenAI:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.chat = SimpleNamespace(
                    completions=SimpleNamespace(create=AsyncMock())
                )

        import sys

        fake_module = SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI)
        monkeypatch.setitem(sys.modules, "openai", fake_module)

        provider = create_provider(
            provider="zhipu", model="glm-4-long", api_key="test"
        )
        assert provider.model_name == "glm-4-long"

    # Note: This class previously asserted Anthropic still raised
    # NotImplementedError. Buffer Day 59 (Agent A) landed AnthropicProvider
    # — see agentcook-providers/tests/test_anthropic_provider.py for the
    # live coverage. The factory.py "Supported:" string update keeps the
    # ValueError branch test below in test_unknown_provider_raises honest.


# ---------------------------------------------------------------------------
# 5. Inherited chat() works (sanity, not a full re-test of OpenAIProvider)
# ---------------------------------------------------------------------------


class TestInheritedChat:
    async def test_chat_via_mock_client(self):
        provider = _build_mock_provider(_fake_completion(), model="glm-4-flash")
        response = await provider.chat([Message(role="user", content="你好")])
        assert response.message.content == "你好"
        assert response.usage.input == 10
        assert response.usage.output == 5
        assert response.finish_reason == "stop"
