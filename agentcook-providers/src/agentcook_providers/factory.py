"""Factory for creating ``LLMProviderProtocol`` instances.

Lazy-imports each vendor SDK so ``pip install agentcook-providers[openai]``
gives you only the deps you asked for. Configuration precedence is
explicit args > environment variables > sensible defaults.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from typing import Any

from agentcook_core import LLMProviderProtocol

logger = logging.getLogger(__name__)

_DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-6",
    "qwen": "qwen-turbo",
    "zhipu": "glm-4-flash",
    "echo": "echo-v0",
    "mock": "mock-agent",
}

SUPPORTED_PROVIDERS: tuple[str, ...] = ("openai", "qwen", "zhipu", "anthropic", "mock", "echo")


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
                     ``mock`` / ``echo``. If omitted, falls back to
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
            api_key=kwargs.pop("api_key", None)
            or _env("QWEN_API_KEY")
            or _env("DASHSCOPE_API_KEY"),
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

    if provider == "mock":
        from agentcook_providers.mock_provider import MockProvider

        delay_ms = kwargs.pop("delay_ms", None)
        if delay_ms is None:
            delay_ms = float(_env("AGENTCOOK_MOCK_DELAY_MS") or 0)
        return MockProvider(model=model or _DEFAULT_MODELS["mock"], delay=float(delay_ms) / 1000)

    if provider == "zhipu":
        from agentcook_providers.zhipu_provider import ZhipuProvider

        return ZhipuProvider(
            model=model or _env("ZHIPU_MODEL") or _DEFAULT_MODELS["zhipu"],
            api_key=kwargs.pop("api_key", None) or _env("ZHIPU_API_KEY"),
            base_url=kwargs.pop("base_url", None) or _env("ZHIPU_BASE_URL"),
            **kwargs,
        )

    if provider == "anthropic":
        from agentcook_providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            model=model or _env("ANTHROPIC_MODEL") or _DEFAULT_MODELS["anthropic"],
            api_key=kwargs.pop("api_key", None) or _env("ANTHROPIC_API_KEY"),
            **kwargs,
        )

    raise ValueError(
        f"Unknown LLM provider: {provider!r}. Supported: {', '.join(SUPPORTED_PROVIDERS)}."
    )


def create_provider_chain(
    spec: str | Sequence[str],
    **kwargs: Any,
) -> LLMProviderProtocol:
    """Build a provider — or a :class:`FallbackProvider` chain — from a spec.

    ``spec`` is a comma-separated list (or sequence) of provider names,
    each optionally pinned to a model with ``name:model``::

        create_provider_chain("qwen:qwen-plus, zhipu:glm-4-flash, mock")

    A single entry returns that provider directly. Entries whose SDK
    extra is not installed are skipped with a warning so a partially
    provisioned environment still serves traffic.
    """
    from agentcook_providers.fallback import FallbackProvider

    entries = [e.strip() for e in (spec.split(",") if isinstance(spec, str) else spec)]
    providers: list[LLMProviderProtocol] = []
    errors: list[str] = []
    for entry in filter(None, entries):
        name, _, model = entry.partition(":")
        try:
            providers.append(create_provider(name.strip(), model.strip() or None, **kwargs))
        except ImportError as exc:
            errors.append(f"{entry}: {exc}")
            logger.warning("Skipping provider %r: %s", entry, exc)
    if not providers:
        raise ValueError(f"No usable provider in chain {spec!r}: {'; '.join(errors) or 'empty'}")
    if len(providers) == 1:
        return providers[0]
    return FallbackProvider(providers)


__all__ = ["SUPPORTED_PROVIDERS", "create_provider", "create_provider_chain"]
