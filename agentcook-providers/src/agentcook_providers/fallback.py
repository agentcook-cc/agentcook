"""Fallback chain over multiple ``LLMProviderProtocol`` instances.

Lifted from phoenix-agent's ``FallbackLLM`` pattern (which itself follows
openclaw's ``runWithModelFallback``). The composition is engine-agnostic
— this module only depends on the core protocol surface.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Sequence

from agentcook_core import (
    ChatChunk,
    ChatResponse,
    LLMProviderProtocol,
    Message,
    ToolProtocol,
)

logger = logging.getLogger(__name__)

DEFAULT_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504, 529})
DEFAULT_RETRYABLE_KEYWORDS: tuple[str, ...] = (
    "overloaded",
    "rate limit",
    "capacity",
    "try again",
    "temporarily unavailable",
)


class FallbackProvider:
    """Try providers in order; on retryable failure, fall through to the next.

    Composes any sequence of objects satisfying :class:`LLMProviderProtocol`
    — including another ``FallbackProvider`` for nested chains. Itself
    satisfies the protocol so call sites stay uniform.

    Failure policy:
    - HTTP 429 / 5xx (configurable) → fallback
    - Substring match against ``"overloaded"`` / ``"rate limit"`` etc.
      → fallback (catches vendor-specific message text without status)
    - Anything else → re-raise immediately (don't mask logic bugs)
    """

    def __init__(
        self,
        providers: Sequence[LLMProviderProtocol],
        *,
        retryable_status_codes: frozenset[int] | None = None,
        retryable_keywords: tuple[str, ...] | None = None,
    ) -> None:
        if not providers:
            raise ValueError("FallbackProvider requires at least one provider.")
        self._providers: tuple[LLMProviderProtocol, ...] = tuple(providers)
        self._retryable_codes = retryable_status_codes or DEFAULT_RETRYABLE_STATUS_CODES
        self._retryable_keywords = retryable_keywords or DEFAULT_RETRYABLE_KEYWORDS

    @property
    def model_name(self) -> str:
        return self._providers[0].model_name

    @property
    def context_window(self) -> int:
        return self._providers[0].context_window

    def count_tokens(self, text: str) -> int:
        return self._providers[0].count_tokens(text)

    def _is_retryable(self, exc: BaseException) -> bool:
        status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
        if status in self._retryable_codes:
            return True
        msg = str(exc).lower()
        return any(kw in msg for kw in self._retryable_keywords)

    async def chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolProtocol] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        last_exc: BaseException | None = None
        for i, provider in enumerate(self._providers):
            try:
                return await provider.chat(
                    messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as exc:
                last_exc = exc
                if i < len(self._providers) - 1 and self._is_retryable(exc):
                    next_name = self._providers[i + 1].model_name
                    logger.warning(
                        "Provider %s failed (%s); falling back to %s",
                        provider.model_name,
                        exc,
                        next_name,
                    )
                    continue
                raise
        assert last_exc is not None
        raise last_exc

    async def stream_chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolProtocol] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        last_exc: BaseException | None = None
        for i, provider in enumerate(self._providers):
            try:
                async for chunk in provider.stream_chat(
                    messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    yield chunk
                return
            except Exception as exc:
                last_exc = exc
                if i < len(self._providers) - 1 and self._is_retryable(exc):
                    next_name = self._providers[i + 1].model_name
                    logger.warning(
                        "Provider %s stream failed (%s); falling back to %s",
                        provider.model_name,
                        exc,
                        next_name,
                    )
                    continue
                raise
        assert last_exc is not None
        raise last_exc


__all__ = [
    "DEFAULT_RETRYABLE_KEYWORDS",
    "DEFAULT_RETRYABLE_STATUS_CODES",
    "FallbackProvider",
]
