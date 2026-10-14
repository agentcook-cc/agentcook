"""agentcook-providers: LLM Provider adapters.

Public API:

- :class:`EchoProvider`      — zero-dep teaching stub / test fixture.
- :class:`OpenAIProvider`    — reference adapter for OpenAI Chat Completions.
- :class:`ZhipuProvider`     — Zhipu GLM-series, OpenAI-compatible (Phase 5 Day 54).
- :class:`AnthropicProvider` — Claude (independent — not OpenAI-compatible) (Buffer Day 59).
- :class:`MockProvider`      — deterministic offline model that drives the
  real agent loop (tool calls included) without any API key.
- :class:`FallbackProvider`  — composes a chain of providers with retry on
  rate-limit / 5xx / overload errors.
- :func:`create_provider`    — factory wired to env vars + lazy imports.
- :func:`create_provider_chain` — ``"qwen,zhipu,mock"`` → fallback chain.

Qwen (DashScope) uses :class:`OpenAIProvider` directly via the factory
(``base_url`` points at the compatible endpoint). All four real
providers are now wired into the factory — the placeholder branch is
gone.
"""

from __future__ import annotations

from agentcook_providers.anthropic_provider import AnthropicProvider
from agentcook_providers.echo_provider import EchoProvider
from agentcook_providers.factory import (
    SUPPORTED_PROVIDERS,
    ProviderConfigError,
    create_provider,
    create_provider_chain,
)
from agentcook_providers.fallback import FallbackProvider
from agentcook_providers.mock_provider import MockProvider
from agentcook_providers.openai_provider import OpenAIProvider
from agentcook_providers.zhipu_provider import ZhipuProvider

__version__ = "0.2.0"

__all__ = [
    "AnthropicProvider",
    "EchoProvider",
    "FallbackProvider",
    "MockProvider",
    "OpenAIProvider",
    "ProviderConfigError",
    "SUPPORTED_PROVIDERS",
    "ZhipuProvider",
    "__version__",
    "create_provider",
    "create_provider_chain",
]
