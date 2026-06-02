"""agentcook-providers: LLM Provider adapters.

Public API:

- :class:`EchoProvider`     — zero-dep teaching stub / test fixture.
- :class:`OpenAIProvider`   — reference adapter for OpenAI Chat Completions.
- :class:`ZhipuProvider`    — Zhipu GLM-series, OpenAI-compatible (Phase 5 Day 54).
- :class:`FallbackProvider` — composes a chain of providers with retry on
  rate-limit / 5xx / overload errors.
- :func:`create_provider`   — factory wired to env vars + lazy imports.

Qwen (DashScope) uses :class:`OpenAIProvider` directly via the factory
(``base_url`` points at the compatible endpoint). Anthropic remains a
Phase 6 backlog placeholder — the factory raises ``NotImplementedError``.
"""

from __future__ import annotations

from agentcook_providers.echo_provider import EchoProvider
from agentcook_providers.factory import create_provider
from agentcook_providers.fallback import FallbackProvider
from agentcook_providers.openai_provider import OpenAIProvider
from agentcook_providers.zhipu_provider import ZhipuProvider

__version__ = "0.1.0"

__all__ = [
    "EchoProvider",
    "FallbackProvider",
    "OpenAIProvider",
    "ZhipuProvider",
    "__version__",
    "create_provider",
]
