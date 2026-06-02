"""Zhipu (智谱) ``LLMProviderProtocol`` adapter.

Zhipu's GLM series exposes an OpenAI-compatible endpoint at
``https://open.bigmodel.cn/api/paas/v4`` — the wire format (request /
response / streaming SSE) is the same as OpenAI Chat Completions, so
we reuse :class:`OpenAIProvider` rather than duplicating the 320-line
adapter (same pattern as Qwen on DashScope, see
``factory.py:create_provider("qwen")``).

This module exists for three reasons that don't fit the factory branch:

1. **GLM-series context windows** — `glm-4-flash` / `glm-4` / `glm-4-air`
   have specific limits the OpenAI default table doesn't know about.
2. **Discoverability** — importing ``ZhipuProvider`` is more obvious
   than calling ``OpenAIProvider(base_url="...")`` from user code.
3. **ADR-018 tiered-model fallback chain** — the planned
   ``qwen-turbo → glm-4-flash → qwen-plus → echo`` chain needs a
   stable ``ZhipuProvider`` class name to construct, even though the
   implementation is one constructor call away from OpenAIProvider.

If Zhipu later diverges from OpenAI wire format (custom function-call
shape, etc), subclass-override the relevant methods here instead of
forking the OpenAIProvider source.
"""

from __future__ import annotations

import os
from typing import Any

from agentcook_providers.openai_provider import OpenAIProvider

ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

# GLM context windows (Zhipu published values). Extend as new models ship.
_ZHIPU_CONTEXT_WINDOWS: dict[str, int] = {
    "glm-4-flash": 128_000,
    "glm-4-air": 128_000,
    "glm-4-airx": 8_000,
    "glm-4-long": 1_000_000,
    "glm-4-plus": 128_000,
    "glm-4-0520": 128_000,
    "glm-4": 128_000,
    "glm-3-turbo": 128_000,
}

DEFAULT_ZHIPU_MODEL = "glm-4-flash"


class ZhipuProvider(OpenAIProvider):
    """Zhipu GLM provider satisfying ``LLMProviderProtocol``.

    Thin subclass of :class:`OpenAIProvider` pinning the Zhipu
    OpenAI-compatible base URL and providing GLM context window
    lookups. All chat / stream_chat / tool-call behaviour inherits
    unchanged — Zhipu's wire format matches OpenAI for the surface
    this adapter exposes.
    """

    def __init__(
        self,
        model: str = DEFAULT_ZHIPU_MODEL,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        **client_kwargs: Any,
    ) -> None:
        super().__init__(
            model=model,
            api_key=api_key,
            base_url=base_url or ZHIPU_BASE_URL,
            **client_kwargs,
        )

    @property
    def context_window(self) -> int:
        """GLM-specific context limit, falling back to OpenAI table."""
        return _ZHIPU_CONTEXT_WINDOWS.get(self._model, super().context_window)

    @classmethod
    def from_env(
        cls,
        model: str | None = None,
        **client_kwargs: Any,
    ) -> ZhipuProvider:
        """Build a ZhipuProvider from env vars.

        Reads:
        - ``ZHIPU_API_KEY`` (required) — your Zhipu open-platform API key.
        - ``ZHIPU_MODEL`` (optional) — overrides the ``glm-4-flash`` default.
        - ``ZHIPU_BASE_URL`` (optional) — overrides the public endpoint
          (rarely needed; useful for proxies or private deployments).

        :raises ValueError: ``ZHIPU_API_KEY`` not set in environment.
        """
        api_key = os.environ.get("ZHIPU_API_KEY")
        if not api_key:
            raise ValueError(
                "ZhipuProvider.from_env(): ZHIPU_API_KEY is required."
            )
        return cls(
            model=model or os.environ.get("ZHIPU_MODEL") or DEFAULT_ZHIPU_MODEL,
            api_key=api_key,
            base_url=os.environ.get("ZHIPU_BASE_URL"),
            **client_kwargs,
        )


__all__ = ["ZHIPU_BASE_URL", "DEFAULT_ZHIPU_MODEL", "ZhipuProvider"]
