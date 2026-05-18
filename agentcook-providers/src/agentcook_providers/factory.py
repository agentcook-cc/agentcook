"""Factory for creating ``LLMProviderProtocol`` instances.

Lazy-imports each vendor SDK so ``pip install agentcook-providers[openai]``
gives you only the deps you asked for. Configuration precedence is
explicit args > environment variables > sensible defaults.
"""

from __future__ import annotations

import os
from typing import Any

from agentcook_core import LLMProviderProtocol

_DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-6",
    "qwen": "qwen-plus",
    "zhipu": "glm-4-flash",
    "echo": "echo-v0",
}


def _env(name: str) -> str | None:
    val = os.environ.get(name)
    return val.strip() if val else None


def create_provider(
    provider: str | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> LLMProviderProtocol:
    """Build a provider matching :class:`LLMProviderProtocol`.

    :param provider: ``openai`` / ``anthropic`` / ``qwen`` / ``zhipu`` /
                     ``echo``. If omitted, falls back to
                     ``AGENTCOOK_LLM_PROVIDER`` env var.
    :param model:    Vendor-specific model id. If omitted, uses the env
                     var ``{PROVIDER}_MODEL`` then a vendor default.
    :raises ValueError:    Unknown / missing provider.
    :raises ImportError:   Vendor extra not installed.
    :raises NotImplementedError: Provider listed but adapter not landed yet.
    """
    provider = (provider or _env("AGENTCOOK_LLM_PROVIDER") or "").lower()
    if not provider:
        raise ValueError(
            "No LLM provider configured. Pass provider= or set "
            "AGENTCOOK_LLM_PROVIDER (e.g. 'openai')."
        )

    if provider == "openai":
        from agentcook_providers.openai_provider import OpenAIProvider

        return OpenAIProvider(
            model=model or _env("OPENAI_MODEL") or _DEFAULT_MODELS["openai"],
            api_key=kwargs.pop("api_key", None) or _env("OPENAI_API_KEY"),
            base_url=kwargs.pop("base_url", None) or _env("OPENAI_BASE_URL"),
            **kwargs,
        )

    if provider == "qwen":
        # Qwen exposes an OpenAI-compatible endpoint; reuse OpenAIProvider.
        from agentcook_providers.openai_provider import OpenAIProvider

        return OpenAIProvider(
            model=model or _env("QWEN_MODEL") or _DEFAULT_MODELS["qwen"],
            api_key=kwargs.pop("api_key", None) or _env("QWEN_API_KEY") or _env("DASHSCOPE_API_KEY"),
            base_url=(
                kwargs.pop("base_url", None)
                or _env("QWEN_BASE_URL")
                or "https://dashscope.aliyuncs.com/compatible-mode/v1"
            ),
            **kwargs,
        )

    if provider == "echo":
        from agentcook_providers.echo_provider import EchoProvider

        return EchoProvider(model=model or _DEFAULT_MODELS["echo"])

    if provider == "anthropic":
        raise NotImplementedError(
            "Anthropic provider lands on Day 9 — see _internal/agent-a-day-7-providers-sketch.md"
        )

    if provider == "zhipu":
        raise NotImplementedError(
            "Zhipu provider lands on Day 9-10 — see _internal/agent-a-day-7-providers-sketch.md"
        )

    raise ValueError(
        f"Unknown LLM provider: {provider!r}. "
        "Supported: 'openai', 'anthropic', 'qwen', 'zhipu', 'echo'."
    )


__all__ = ["create_provider"]
