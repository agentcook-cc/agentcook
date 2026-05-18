"""agentcook-providers: LLM Provider adapters.

Public API:

- :class:`EchoProvider`     — zero-dep teaching stub / test fixture.
- :class:`OpenAIProvider`   — reference adapter for OpenAI Chat Completions
  (also drives Qwen via the OpenAI-compatible DashScope endpoint).
- :class:`FallbackProvider` — composes a chain of providers with retry on
  rate-limit / 5xx / overload errors.
- :func:`create_provider`   — factory wired to env vars + lazy imports.

Anthropic and Zhipu adapters land in Day 9-10; the factory raises
:class:`NotImplementedError` for them today.
"""

from __future__ import annotations

from agentcook_providers.echo_provider import EchoProvider
from agentcook_providers.factory import create_provider
from agentcook_providers.fallback import FallbackProvider
from agentcook_providers.openai_provider import OpenAIProvider

__version__ = "0.1.0"

__all__ = [
    "EchoProvider",
    "FallbackProvider",
    "OpenAIProvider",
    "__version__",
    "create_provider",
]
