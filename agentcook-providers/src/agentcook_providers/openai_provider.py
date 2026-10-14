"""OpenAI ``LLMProviderProtocol`` adapter.

Reference implementation against the official ``openai`` SDK
(``AsyncOpenAI`` client). Doubles as the Qwen adapter — Tongyi exposes an
OpenAI-compatible endpoint, so callers point ``base_url`` at DashScope and
reuse this class.

The implementation deliberately keeps no provider-specific state on the
class — ``_message_to_openai`` / ``_openai_to_message`` are pure helpers
so they can be unit-tested without a live client.
"""

from __future__ import annotations

import json
import time
import uuid
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
    from openai import AsyncOpenAI

# Approximate context windows. Extend as new models ship.
_CONTEXT_WINDOWS: dict[str, int] = {
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4": 8_192,
    "gpt-3.5-turbo": 16_385,
    "o1": 200_000,
    "o1-mini": 128_000,
    "o3-mini": 200_000,
    # Qwen on DashScope OpenAI-compatible endpoint
    "qwen-plus": 131_072,
    "qwen-turbo": 8_000,
    "qwen-max": 32_000,
}
DEFAULT_CONTEXT_WINDOW = 128_000


def _tools_to_openai(tools: Sequence[ToolProtocol]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters_schema,
            },
        }
        for t in tools
    ]


def _parse_arguments(raw: str | None) -> dict[str, Any]:
    """Decode a tool-call argument string without ever raising.

    Models occasionally emit malformed JSON. Surfacing it as a ``_raw``
    argument lets the agent loop return a precise validation error the
    model can self-correct from, instead of crashing the stream.
    """
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw}
    return parsed if isinstance(parsed, dict) else {"_raw": raw}


def _message_to_openai(msg: Message) -> dict[str, Any]:
    """Convert an internal :class:`Message` to OpenAI's ChatML dict shape."""
    d: dict[str, Any] = {"role": msg.role, "content": msg.content}
    # ``name`` is only meaningful on user/system/assistant turns; several
    # OpenAI-compatible backends reject it on ``tool`` messages.
    if msg.name is not None and msg.role != "tool":
        d["name"] = msg.name
    if msg.tool_calls:
        d["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.name,
                    "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                },
            }
            for tc in msg.tool_calls
        ]
        # Assistant turns that issue tool_calls should send empty content (not None)
        # — OpenAI accepts "" but rejects null when tool_calls are present.
        if msg.content == "":
            d["content"] = None
    if msg.role == "tool":
        d["tool_call_id"] = msg.tool_call_id
    return d


def _openai_to_chat_response(completion: Any) -> ChatResponse:
    choice = completion.choices[0]
    raw_msg = choice.message
    tool_calls: tuple[ToolCall, ...] | None = None
    if raw_msg.tool_calls:
        tool_calls = tuple(
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=_parse_arguments(tc.function.arguments),
            )
            for tc in raw_msg.tool_calls
        )
    message = Message(
        role="assistant",
        content=raw_msg.content or "",
        tool_calls=tool_calls,
    )
    usage = _usage_from(completion.usage)
    finish: FinishReason | None = None
    if choice.finish_reason in ("stop", "length", "tool_calls", "content_filter"):
        finish = choice.finish_reason  # type: ignore[assignment]
    return ChatResponse(message=message, usage=usage, finish_reason=finish)


def _usage_from(raw: Any) -> TokenUsage:
    if raw is None:
        return TokenUsage()
    details = getattr(raw, "prompt_tokens_details", None)
    return TokenUsage(
        input=getattr(raw, "prompt_tokens", 0) or 0,
        output=getattr(raw, "completion_tokens", 0) or 0,
        cached=(getattr(details, "cached_tokens", 0) or 0) if details is not None else 0,
    )


class OpenAIProvider:
    """OpenAI Chat Completions provider satisfying ``LLMProviderProtocol``.

    Also serves every OpenAI-compatible backend (Qwen/DashScope, Zhipu,
    DeepSeek, vLLM, Ollama …) via ``base_url``.

    Args:
        stream_usage: Request ``stream_options.include_usage`` so the
            final streamed chunk carries token accounting. Disable for
            backends that reject the option.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        client: AsyncOpenAI | None = None,
        stream_usage: bool = True,
        **client_kwargs: Any,
    ) -> None:
        self._model = model
        self._stream_usage = stream_usage
        if client is not None:
            self._client = client
        else:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:
                raise ImportError(
                    "Install agentcook-providers[openai] to use OpenAIProvider."
                ) from exc
            self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, **client_kwargs)

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def context_window(self) -> int:
        return _CONTEXT_WINDOWS.get(self._model, DEFAULT_CONTEXT_WINDOW)

    def count_tokens(self, text: str) -> int:
        try:
            import tiktoken
        except ImportError:
            return max(1, estimate_tokens(text))
        try:
            enc = tiktoken.encoding_for_model(self._model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))

    async def chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolProtocol] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        with get_tracer().start_span(
            "model.openai.chat",
            attributes={
                "agentcook.model.name": self._model,
                "agentcook.model.provider": "openai",
                "agentcook.messages.count": len(messages),
                "agentcook.tools.count": len(tools) if tools else 0,
            },
        ) as span:
            api_messages = [_message_to_openai(m) for m in messages]
            kwargs: dict[str, Any] = {"model": self._model, "messages": api_messages}
            if tools:
                kwargs["tools"] = _tools_to_openai(tools)
            if temperature is not None:
                kwargs["temperature"] = temperature
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            started_ns = time.perf_counter_ns()
            completion = await self._client.chat.completions.create(**kwargs)
            latency_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
            response = _openai_to_chat_response(completion)
            span.set_attribute("agentcook.tokens.in", response.usage.input)
            span.set_attribute("agentcook.tokens.out", response.usage.output)
            span.set_attribute("agentcook.tokens.total", response.usage.total)
            span.set_attribute("agentcook.latency_ms", latency_ms)
            if response.finish_reason:
                span.set_attribute("agentcook.finish_reason", response.finish_reason)

            # Langfuse: report the real model call — has the full picture
            # the lightweight model_router.select() event lacks. Errors
            # are swallowed; telemetry must never break the response.
            try:
                last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
                get_langfuse_hook().observe_model_call(
                    model=self._model,
                    provider="openai",
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
                # Provider-side telemetry failure must not crash the chat.
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
        # Span is opened here and closed when the consumer exhausts the
        # generator (or it is GC'd). Streaming responses don't return a
        # final usage on every chunk — we record what the *terminal* chunk
        # carries (or nothing if the API doesn't include it).
        span = get_tracer().start_span(
            "model.openai.stream_chat",
            attributes={
                "agentcook.model.name": self._model,
                "agentcook.model.provider": "openai",
                "agentcook.messages.count": len(messages),
                "agentcook.tools.count": len(tools) if tools else 0,
                "agentcook.stream": True,
            },
        )
        span.__enter__()
        chunks_yielded = 0
        try:
            api_messages = [_message_to_openai(m) for m in messages]
            kwargs: dict[str, Any] = {
                "model": self._model,
                "messages": api_messages,
                "stream": True,
            }
            if self._stream_usage:
                kwargs["stream_options"] = {"include_usage": True}
            if tools:
                kwargs["tools"] = _tools_to_openai(tools)
            if temperature is not None:
                kwargs["temperature"] = temperature
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens

            stream = await self._client.chat.completions.create(**kwargs)

            accumulated: dict[int, dict[str, str]] = {}
            emitted_calls = False
            usage: TokenUsage | None = None
            last_finish: FinishReason | None = None

            def flush_calls() -> tuple[ToolCall, ...]:
                return tuple(
                    ToolCall(
                        id=slot["id"],
                        name=slot["name"],
                        arguments=_parse_arguments(slot["arguments"]),
                    )
                    for _, slot in sorted(accumulated.items())
                )

            async for chunk in stream:  # type: ignore[union-attr]
                raw_usage = getattr(chunk, "usage", None)
                if raw_usage is not None:
                    usage = _usage_from(raw_usage)
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                finish_raw = chunk.choices[0].finish_reason
                finish: FinishReason | None = None
                if finish_raw in ("stop", "length", "tool_calls", "content_filter"):
                    finish = finish_raw  # type: ignore[assignment]

                if delta and delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index if tc_delta.index is not None else len(accumulated)
                        slot = accumulated.setdefault(
                            idx,
                            {
                                "id": tc_delta.id or f"call_{uuid.uuid4().hex[:8]}",
                                "name": "",
                                "arguments": "",
                            },
                        )
                        if tc_delta.function:
                            if tc_delta.function.name:
                                slot["name"] += tc_delta.function.name
                            if tc_delta.function.arguments:
                                slot["arguments"] += tc_delta.function.arguments

                # Some OpenAI-compatible backends finish tool turns with
                # "stop" instead of "tool_calls" — emit on any finish.
                new_tool_calls: tuple[ToolCall, ...] = ()
                if finish and accumulated and not emitted_calls:
                    new_tool_calls = flush_calls()
                    emitted_calls = True
                    finish = "tool_calls"

                if finish:
                    last_finish = finish
                    span.set_attribute("agentcook.finish_reason", finish)

                content = (delta.content if delta and delta.content else "") or ""
                if content or new_tool_calls or finish:
                    chunks_yielded += 1
                    yield ChatChunk(
                        delta_content=content,
                        delta_tool_calls=new_tool_calls,
                        finish_reason=finish,
                    )

            trailing_calls: tuple[ToolCall, ...] = ()
            if accumulated and not emitted_calls:
                trailing_calls = flush_calls()
                last_finish = "tool_calls"
            if usage is not None or trailing_calls:
                if usage is not None:
                    span.set_attribute("agentcook.tokens.in", usage.input)
                    span.set_attribute("agentcook.tokens.out", usage.output)
                chunks_yielded += 1
                yield ChatChunk(
                    delta_tool_calls=trailing_calls,
                    finish_reason=last_finish if trailing_calls else None,
                    usage=usage,
                )
        finally:
            span.set_attribute("agentcook.stream.chunks", chunks_yielded)
            span.__exit__(None, None, None)


__all__ = ["OpenAIProvider"]
