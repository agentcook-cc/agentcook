"""Anthropic Claude ``LLMProviderProtocol`` adapter.

Independent implementation — Claude API does **not** share the OpenAI
wire format, so the Zhipu-style thin subclass pattern doesn't apply
here. Three concrete divergences:

1. ``messages.create`` instead of ``chat.completions.create``
2. ``system`` is a top-level parameter, not a ``{"role": "system"}`` entry
3. Streaming uses ``content_block_delta`` events rather than
   ``choices[0].delta``; ``stop_reason`` is a different enum
   (``end_turn`` / ``max_tokens`` / ``tool_use`` / ``stop_sequence``)

Scope of v1.1 (Buffer Day 59, ADR-002 / Day 9-10 backlog closure):
    Text chat + streaming. Tool-use is **not** implemented — Phase 6
    backlog. Callers requesting tools get an empty ``delta_tool_calls``
    tuple in every chunk; no provider-side conversion runs.

Day 59 work follows the OpenAIProvider style for tracing / Langfuse
hook so the existing observability stack picks Anthropic up unchanged.
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator, Sequence
from typing import TYPE_CHECKING, Any

from agentcook_core import (
    ChatChunk,
    ChatResponse,
    FinishReason,
    Message,
    TokenUsage,
    ToolProtocol,
)
from agentcook_core.langfuse_hook import get_langfuse_hook
from agentcook_core.tracing import get_tracer

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic

# Approximate context windows. Extend as new models ship.
_CONTEXT_WINDOWS: dict[str, int] = {
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-5-haiku-20241022": 200_000,
    "claude-3-opus-20240229": 200_000,
    "claude-3-sonnet-20240229": 200_000,
    "claude-3-haiku-20240307": 200_000,
    "claude-sonnet-4-5": 200_000,
    "claude-sonnet-4-6": 200_000,
    "claude-opus-4-7": 200_000,
}
DEFAULT_CONTEXT_WINDOW = 200_000

# Anthropic requires max_tokens on every call. Use a sensible default
# when the caller doesn't specify (OpenAI lets you omit it).
DEFAULT_MAX_TOKENS = 4_096

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"


def _split_system_messages(
    messages: Sequence[Message],
) -> tuple[str | None, list[dict[str, Any]]]:
    """Split system messages out of the conversation.

    Anthropic takes ``system`` as a top-level string parameter rather
    than a message with role=system. Multiple system messages get
    concatenated with double newlines (matches Anthropic's documented
    behaviour for system-block lists).
    """
    system_parts: list[str] = []
    anthropic_messages: list[dict[str, Any]] = []
    for msg in messages:
        if msg.role == "system":
            system_parts.append(msg.content)
        else:
            anthropic_messages.append(
                {"role": msg.role, "content": msg.content}
            )
    system = "\n\n".join(system_parts) if system_parts else None
    return system, anthropic_messages


_STOP_REASON_MAP: dict[str, FinishReason] = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
}


def _stop_reason_to_finish(stop_reason: str | None) -> FinishReason | None:
    if stop_reason is None:
        return None
    return _STOP_REASON_MAP.get(stop_reason)


def _anthropic_to_chat_response(message: Any) -> ChatResponse:
    # message.content is a list of content blocks; collect text blocks only
    # (tool_use blocks are not surfaced in v1.1 — Phase 6 backlog).
    text_parts = [
        block.text for block in (message.content or [])
        if getattr(block, "type", None) == "text" and getattr(block, "text", None)
    ]
    content = "".join(text_parts)
    usage = TokenUsage(
        input=getattr(message.usage, "input_tokens", 0) or 0,
        output=getattr(message.usage, "output_tokens", 0) or 0,
    )
    finish = _stop_reason_to_finish(getattr(message, "stop_reason", None))
    return ChatResponse(
        message=Message(role="assistant", content=content),
        usage=usage,
        finish_reason=finish,
    )


class AnthropicProvider:
    """Anthropic Claude chat provider satisfying ``LLMProviderProtocol``."""

    def __init__(
        self,
        model: str = DEFAULT_ANTHROPIC_MODEL,
        *,
        api_key: str | None = None,
        client: AsyncAnthropic | None = None,
        **client_kwargs: Any,
    ) -> None:
        self._model = model
        if client is not None:
            self._client = client
        else:
            try:
                from anthropic import AsyncAnthropic
            except ImportError as exc:
                raise ImportError(
                    "Install agentcook-providers[anthropic] to use AnthropicProvider."
                ) from exc
            self._client = AsyncAnthropic(api_key=api_key, **client_kwargs)

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def context_window(self) -> int:
        return _CONTEXT_WINDOWS.get(self._model, DEFAULT_CONTEXT_WINDOW)

    def count_tokens(self, text: str) -> int:
        # Anthropic SDK exposes a remote count_tokens endpoint, but it
        # costs an API call. Use a 4-char-per-token heuristic for
        # offline / fast-path use; callers needing exact counts can
        # call self._client.messages.count_tokens() directly.
        return max(1, len(text) // 4)

    @classmethod
    def from_env(
        cls,
        model: str | None = None,
        **client_kwargs: Any,
    ) -> AnthropicProvider:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "AnthropicProvider.from_env(): ANTHROPIC_API_KEY is required."
            )
        return cls(
            model=model or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL,
            api_key=api_key,
            **client_kwargs,
        )

    async def chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolProtocol] | None = None,  # noqa: ARG002 — v1.1 ignores; Phase 6 backlog
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        with get_tracer().start_span(
            "model.anthropic.chat",
            attributes={
                "agentcook.model.name": self._model,
                "agentcook.model.provider": "anthropic",
                "agentcook.messages.count": len(messages),
                "agentcook.tools.count": 0,  # v1.1 ignores tools
            },
        ) as span:
            system, api_messages = _split_system_messages(messages)
            kwargs: dict[str, Any] = {
                "model": self._model,
                "messages": api_messages,
                "max_tokens": max_tokens or DEFAULT_MAX_TOKENS,
            }
            if system is not None:
                kwargs["system"] = system
            if temperature is not None:
                kwargs["temperature"] = temperature

            started_ns = time.perf_counter_ns()
            message = await self._client.messages.create(**kwargs)
            latency_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
            response = _anthropic_to_chat_response(message)
            span.set_attribute("agentcook.tokens.in", response.usage.input)
            span.set_attribute("agentcook.tokens.out", response.usage.output)
            span.set_attribute("agentcook.tokens.total", response.usage.total)
            span.set_attribute("agentcook.latency_ms", latency_ms)
            if response.finish_reason:
                span.set_attribute("agentcook.finish_reason", response.finish_reason)

            try:
                last_user = next(
                    (m.content for m in reversed(messages) if m.role == "user"), ""
                )
                get_langfuse_hook().observe_model_call(
                    model=self._model,
                    provider="anthropic",
                    prompt=last_user,
                    completion=response.message.content,
                    prompt_tokens=response.usage.input,
                    completion_tokens=response.usage.output,
                    latency_ms=latency_ms,
                    metadata={
                        "event": "model.chat",
                        "finish_reason": response.finish_reason or "",
                        "messages_count": len(messages),
                        "tools_count": 0,
                    },
                )
            except Exception:
                pass
            return response

    async def stream_chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolProtocol] | None = None,  # noqa: ARG002 — v1.1 ignores
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        span = get_tracer().start_span(
            "model.anthropic.stream_chat",
            attributes={
                "agentcook.model.name": self._model,
                "agentcook.model.provider": "anthropic",
                "agentcook.messages.count": len(messages),
                "agentcook.tools.count": 0,
                "agentcook.stream": True,
            },
        )
        span.__enter__()
        chunks_yielded = 0
        try:
            system, api_messages = _split_system_messages(messages)
            kwargs: dict[str, Any] = {
                "model": self._model,
                "messages": api_messages,
                "max_tokens": max_tokens or DEFAULT_MAX_TOKENS,
            }
            if system is not None:
                kwargs["system"] = system
            if temperature is not None:
                kwargs["temperature"] = temperature

            stream = self._client.messages.stream(**kwargs)
            async with stream as event_stream:
                final_finish: FinishReason | None = None
                async for event in event_stream:
                    event_type = getattr(event, "type", None)
                    if event_type == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if delta is not None and getattr(delta, "type", None) == "text_delta":
                            text = getattr(delta, "text", "") or ""
                            if text:
                                chunks_yielded += 1
                                yield ChatChunk(delta_content=text)
                    elif event_type == "message_delta":
                        delta = getattr(event, "delta", None)
                        if delta is not None:
                            stop_reason = getattr(delta, "stop_reason", None)
                            final_finish = _stop_reason_to_finish(stop_reason)

                if final_finish is not None:
                    span.set_attribute("agentcook.finish_reason", final_finish)
                # Emit a terminal chunk carrying finish_reason — matches the
                # OpenAIProvider pattern so chat.py's _stream_real_response
                # captures the same finish_reason field.
                yield ChatChunk(delta_content="", finish_reason=final_finish)
        finally:
            span.set_attribute("agentcook.stream.chunks", chunks_yielded)
            span.__exit__(None, None, None)


__all__ = [
    "DEFAULT_ANTHROPIC_MODEL",
    "DEFAULT_MAX_TOKENS",
    "AnthropicProvider",
]
