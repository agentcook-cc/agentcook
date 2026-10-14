"""Anthropic Claude ``LLMProviderProtocol`` adapter.

Independent implementation — the Messages API does **not** share the
OpenAI wire format:

1. ``messages.create`` / ``messages.stream`` instead of
   ``chat.completions.create``.
2. ``system`` is a top-level parameter, not a ``{"role": "system"}``
   entry.
3. Tool calls are ``tool_use`` content blocks on the assistant turn and
   tool results are ``tool_result`` blocks on the *next user* turn —
   there is no ``tool`` role. Consecutive same-role turns must be merged.
4. Streaming arrives as typed events: ``content_block_start`` announces
   a text or ``tool_use`` block, ``content_block_delta`` carries
   ``text_delta`` / ``input_json_delta`` fragments,
   ``content_block_stop`` closes it; usage is split between
   ``message_start`` (input) and ``message_delta`` (output).

Full tool use is supported in both ``chat`` and ``stream_chat``; tool
calls are emitted as complete :class:`ToolCall` values once their JSON
input has fully arrived. Prompt caching (``cache_control`` on the system
prompt and the tool list) is on by default — the agent runtime builds
cache-friendly prompts, and Anthropic bills cached prefix reads at a
fraction of the normal input price.
"""

from __future__ import annotations

import json
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
    ToolCall,
    ToolProtocol,
)
from agentcook_core.langfuse_hook import get_langfuse_hook
from agentcook_core.tokens import estimate_tokens
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

_EPHEMERAL = {"type": "ephemeral"}


def _split_system_messages(
    messages: Sequence[Message],
) -> tuple[str | None, list[dict[str, Any]]]:
    """Split system messages out and convert the rest to Anthropic shape.

    - System messages are concatenated (double newline) into one string.
    - Assistant ``tool_calls`` become ``tool_use`` blocks.
    - ``tool`` messages become ``tool_result`` blocks on a user turn.
    - Consecutive turns with the same role are merged (the API requires
      strict user/assistant alternation).

    Plain text turns stay plain strings so simple transcripts round-trip
    unchanged.
    """
    system_parts: list[str] = []
    out: list[dict[str, Any]] = []

    def append(role: str, blocks: list[dict[str, Any]]) -> None:
        if out and out[-1]["role"] == role:
            prev = out[-1]["content"]
            if isinstance(prev, str):
                prev = [{"type": "text", "text": prev}] if prev else []
            out[-1]["content"] = prev + blocks
        elif len(blocks) == 1 and blocks[0]["type"] == "text":
            out.append({"role": role, "content": blocks[0]["text"]})
        else:
            out.append({"role": role, "content": blocks})

    for msg in messages:
        if msg.role == "system":
            system_parts.append(msg.content)
        elif msg.role == "tool":
            append(
                "user",
                [
                    {
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id or "",
                        "content": msg.content,
                        **({"is_error": True} if msg.content.startswith("ERROR:") else {}),
                    }
                ],
            )
        elif msg.role == "assistant":
            blocks: list[dict[str, Any]] = []
            if msg.content:
                blocks.append({"type": "text", "text": msg.content})
            for call in msg.tool_calls or ():
                blocks.append(
                    {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
                )
            if blocks:
                append("assistant", blocks)
        else:
            append("user", [{"type": "text", "text": msg.content}])
    system = "\n\n".join(system_parts) if system_parts else None
    return system, out


def _tools_to_anthropic(
    tools: Sequence[ToolProtocol], *, cache: bool = False
) -> list[dict[str, Any]]:
    converted = [
        {"name": t.name, "description": t.description, "input_schema": t.parameters_schema}
        for t in tools
    ]
    if cache and converted:
        converted[-1] = {**converted[-1], "cache_control": _EPHEMERAL}
    return converted


_STOP_REASON_MAP: dict[str, FinishReason] = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
    "refusal": "content_filter",
}


def _stop_reason_to_finish(stop_reason: str | None) -> FinishReason | None:
    if stop_reason is None:
        return None
    return _STOP_REASON_MAP.get(stop_reason)


def _usage_from(raw: Any) -> TokenUsage:
    if raw is None:
        return TokenUsage()
    cached = getattr(raw, "cache_read_input_tokens", 0) or 0
    created = getattr(raw, "cache_creation_input_tokens", 0) or 0
    return TokenUsage(
        input=(getattr(raw, "input_tokens", 0) or 0) + cached + created,
        output=getattr(raw, "output_tokens", 0) or 0,
        cached=cached,
    )


def _anthropic_to_chat_response(message: Any) -> ChatResponse:
    text_parts: list[str] = []
    calls: list[ToolCall] = []
    for block in message.content or []:
        kind = getattr(block, "type", None)
        if kind == "text" and getattr(block, "text", None):
            text_parts.append(block.text)
        elif kind == "tool_use":
            calls.append(
                ToolCall(
                    id=block.id, name=block.name, arguments=dict(getattr(block, "input", {}) or {})
                )
            )
    return ChatResponse(
        message=Message(
            role="assistant", content="".join(text_parts), tool_calls=tuple(calls) or None
        ),
        usage=_usage_from(getattr(message, "usage", None)),
        finish_reason=_stop_reason_to_finish(getattr(message, "stop_reason", None)),
    )


class AnthropicProvider:
    """Anthropic Claude chat provider satisfying ``LLMProviderProtocol``."""

    def __init__(
        self,
        model: str = DEFAULT_ANTHROPIC_MODEL,
        *,
        api_key: str | None = None,
        client: AsyncAnthropic | None = None,
        prompt_caching: bool = True,
        **client_kwargs: Any,
    ) -> None:
        self._model = model
        self._prompt_caching = prompt_caching
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
        # The SDK's count_tokens endpoint costs a network round-trip; use
        # the local CJK-aware estimate for budgeting decisions.
        return max(1, estimate_tokens(text))

    @classmethod
    def from_env(
        cls,
        model: str | None = None,
        **client_kwargs: Any,
    ) -> AnthropicProvider:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("AnthropicProvider.from_env(): ANTHROPIC_API_KEY is required.")
        return cls(
            model=model or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL,
            api_key=api_key,
            **client_kwargs,
        )

    def _request_kwargs(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolProtocol] | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        system, api_messages = _split_system_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "max_tokens": max_tokens or DEFAULT_MAX_TOKENS,
        }
        if system is not None:
            if self._prompt_caching:
                kwargs["system"] = [{"type": "text", "text": system, "cache_control": _EPHEMERAL}]
            else:
                kwargs["system"] = system
        if tools:
            kwargs["tools"] = _tools_to_anthropic(tools, cache=self._prompt_caching)
        if temperature is not None:
            kwargs["temperature"] = temperature
        return kwargs

    async def chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolProtocol] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        with get_tracer().start_span(
            "model.anthropic.chat",
            attributes={
                "agentcook.model.name": self._model,
                "agentcook.model.provider": "anthropic",
                "agentcook.messages.count": len(messages),
                "agentcook.tools.count": len(tools) if tools else 0,
            },
        ) as span:
            kwargs = self._request_kwargs(messages, tools, temperature, max_tokens)
            started_ns = time.perf_counter_ns()
            message = await self._client.messages.create(**kwargs)
            latency_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
            response = _anthropic_to_chat_response(message)
            span.set_attribute("agentcook.tokens.in", response.usage.input)
            span.set_attribute("agentcook.tokens.out", response.usage.output)
            span.set_attribute("agentcook.tokens.cached", response.usage.cached)
            span.set_attribute("agentcook.tokens.total", response.usage.total)
            span.set_attribute("agentcook.latency_ms", latency_ms)
            if response.finish_reason:
                span.set_attribute("agentcook.finish_reason", response.finish_reason)

            try:
                last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
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
                        "tools_count": len(tools) if tools else 0,
                    },
                )
            except Exception:
                pass
            return response

    async def stream_chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolProtocol] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        span = get_tracer().start_span(
            "model.anthropic.stream_chat",
            attributes={
                "agentcook.model.name": self._model,
                "agentcook.model.provider": "anthropic",
                "agentcook.messages.count": len(messages),
                "agentcook.tools.count": len(tools) if tools else 0,
                "agentcook.stream": True,
            },
        )
        span.__enter__()
        chunks_yielded = 0
        try:
            kwargs = self._request_kwargs(messages, tools, temperature, max_tokens)
            stream = self._client.messages.stream(**kwargs)
            input_usage = TokenUsage()
            output_tokens = 0
            final_finish: FinishReason | None = None
            # index → {"id", "name", "json"} for in-flight tool_use blocks
            pending: dict[int, dict[str, str]] = {}
            async with stream as event_stream:
                async for event in event_stream:
                    event_type = getattr(event, "type", None)
                    if event_type == "message_start":
                        message = getattr(event, "message", None)
                        input_usage = _usage_from(getattr(message, "usage", None))
                    elif event_type == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if getattr(block, "type", None) == "tool_use":
                            pending[getattr(event, "index", 0)] = {
                                "id": block.id,
                                "name": block.name,
                                "json": "",
                            }
                    elif event_type == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        delta_type = getattr(delta, "type", None)
                        if delta_type == "text_delta":
                            text = getattr(delta, "text", "") or ""
                            if text:
                                chunks_yielded += 1
                                yield ChatChunk(delta_content=text)
                        elif delta_type == "input_json_delta":
                            slot = pending.get(getattr(event, "index", 0))
                            if slot is not None:
                                slot["json"] += getattr(delta, "partial_json", "") or ""
                    elif event_type == "content_block_stop":
                        slot = pending.pop(getattr(event, "index", 0), None)
                        if slot is not None:
                            try:
                                arguments = json.loads(slot["json"]) if slot["json"] else {}
                            except json.JSONDecodeError:
                                arguments = {"_raw": slot["json"]}
                            chunks_yielded += 1
                            yield ChatChunk(
                                delta_tool_calls=(
                                    ToolCall(id=slot["id"], name=slot["name"], arguments=arguments),
                                )
                            )
                    elif event_type == "message_delta":
                        delta = getattr(event, "delta", None)
                        if delta is not None:
                            stop = _stop_reason_to_finish(getattr(delta, "stop_reason", None))
                            if stop is not None:
                                final_finish = stop
                        usage = getattr(event, "usage", None)
                        if usage is not None:
                            output_tokens = getattr(usage, "output_tokens", 0) or output_tokens

            if final_finish is not None:
                span.set_attribute("agentcook.finish_reason", final_finish)
            total_usage = TokenUsage(
                input=input_usage.input, output=output_tokens, cached=input_usage.cached
            )
            span.set_attribute("agentcook.tokens.in", total_usage.input)
            span.set_attribute("agentcook.tokens.out", total_usage.output)
            # Terminal chunk carries finish_reason + usage (OpenAI parity).
            yield ChatChunk(
                delta_content="",
                finish_reason=final_finish,
                usage=total_usage if (total_usage.input or total_usage.output) else None,
            )
        finally:
            span.set_attribute("agentcook.stream.chunks", chunks_yielded)
            span.__exit__(None, None, None)


__all__ = [
    "DEFAULT_ANTHROPIC_MODEL",
    "DEFAULT_MAX_TOKENS",
    "AnthropicProvider",
]
