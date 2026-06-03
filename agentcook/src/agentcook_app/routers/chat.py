"""Chat streaming endpoint.

Implements ``POST /api/v1/chat/stream`` — the primary SSE endpoint for
B's ``useSseChat`` hook.

Phase 4.6 (2026-06-01): Real LLM provider integration via
``agentcook_providers.create_provider()`` — default Qwen qwen-turbo per
ADR-016. Mock generator retained as ``AGENTCOOK_CHAT_MOCK=true`` fallback
for unit/contract tests + offline dev.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from agentcook_app.schemas_chat import ChatStreamFrame, ChatStreamRequest
from agentcook_core.types import Message

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


# --------------------------------------------------------------------------
# Provider singleton — lazy init on first request to avoid import-time cost
# --------------------------------------------------------------------------

_provider_cache: Any = None


def _get_provider() -> Any:
    """Lazy singleton. Reads AGENTCOOK_LLM_PROVIDER + provider-specific env
    vars (QWEN_API_KEY / OPENAI_API_KEY / etc) via agentcook_providers factory.
    """
    global _provider_cache
    if _provider_cache is None:
        from agentcook_providers.factory import create_provider

        _provider_cache = create_provider()
    return _provider_cache


def _use_mock() -> bool:
    """Mock when AGENTCOOK_CHAT_MOCK=true (case-insensitive) or no provider env."""
    flag = os.environ.get("AGENTCOOK_CHAT_MOCK", "").strip().lower()
    if flag in ("true", "1", "yes"):
        return True
    # No provider configured → fall back to mock (CI / contract tests)
    if not os.environ.get("AGENTCOOK_LLM_PROVIDER"):
        return True
    return False


# --------------------------------------------------------------------------
# Mock streaming generator — replaced by real LLM provider in Phase 5
# --------------------------------------------------------------------------

_MOCK_RESPONSES = [
    "I'd be happy to help you with that! ",
    "Let me think about this for a moment.\n\n",
    "Based on my analysis, here's what I suggest:\n\n",
    "1. **First**, we should consider the overall architecture.\n",
    "2. **Second**, let's look at the implementation details.\n",
    "3. **Third**, we can optimize for performance.\n\n",
    "Would you like me to elaborate on any of these points?",
]

_MOCK_PLUGIN_RESPONSE = (
    "I've activated the requested plugins. "
    "Here's what I found using the tools available:\n\n"
    "```python\nresult = plugin.execute(query)\nprint(result)\n```\n\n"
    "The execution completed successfully."
)


async def _stream_mock_response(
    request: ChatStreamRequest,
) -> AsyncIterator[bytes]:
    """Generate mock SSE frames simulating a streaming LLM response.

    Frame format: ``data: {json}\n\n`` (standard SSE wire format).
    Terminal frame has ``done: true`` + metadata (token usage, model).
    """
    session_id = request.session_id
    model_used = request.model or "gpt-4o-mock"

    # First frame: echo session_id
    first_frame = ChatStreamFrame(
        role="assistant",
        content="",
        done=False,
        session_id=session_id,
    )
    yield f"data: {first_frame.model_dump_json()}\n\n".encode()
    await asyncio.sleep(0.05)

    # Content frames: stream response chunks
    if request.plugin_ids:
        chunks = [_MOCK_PLUGIN_RESPONSE]
    else:
        chunks = _MOCK_RESPONSES

    for chunk in chunks:
        # Simulate token-by-token for shorter chunks, or sentence-level
        frame = ChatStreamFrame(role="assistant", content=chunk, done=False)
        yield f"data: {frame.model_dump_json()}\n\n".encode()
        await asyncio.sleep(0.08)

    # Terminal frame: done + metadata
    final_frame = ChatStreamFrame(
        role="assistant",
        content="",
        done=True,
        metadata={
            "model": model_used,
            "usage": {"input_tokens": 42, "output_tokens": len("".join(chunks))},
            "request_id": uuid.uuid4().hex,
            "duration_ms": round(len(chunks) * 80, 1),
            "source": "mock",
        },
    )
    yield f"data: {final_frame.model_dump_json()}\n\n".encode()


# --------------------------------------------------------------------------
# Real LLM streaming generator — Phase 4.6 (2026-06-01)
# Calls agentcook_providers.create_provider().stream_chat() and wraps
# ChatChunk → ChatStreamFrame to preserve B's useSseChat wire format.
# --------------------------------------------------------------------------


async def _stream_real_response(
    request: ChatStreamRequest,
    provider_override: str | None = None,
) -> AsyncIterator[bytes]:
    """Stream a real LLM response via the configured provider (default Qwen).

    Wraps ``provider.stream_chat()`` chunks into ``ChatStreamFrame`` SSE.
    Errors (rate limit / 5xx / timeout) emit a terminal frame with ``error``
    set so the frontend can surface them without breaking the SSE contract.

    :param provider_override: ADR-018 quota resolver hook — when set, builds
        a fresh provider via ``agentcook_providers.create_provider(name)``
        instead of using the cached singleton. ``None`` keeps the
        Phase 4.6 single-provider behaviour.
    """
    session_id = request.session_id
    if provider_override:
        from agentcook_providers.factory import create_provider as _create_provider

        provider = _create_provider(provider=provider_override)
    else:
        provider = _get_provider()
    model_used = request.model or getattr(provider, "model_name", "unknown")

    # First frame: echo session_id (matches mock contract for useSseChat)
    first_frame = ChatStreamFrame(
        role="assistant",
        content="",
        done=False,
        session_id=session_id,
    )
    yield f"data: {first_frame.model_dump_json()}\n\n".encode()

    # Phase 4.6: single-turn (no memory load yet). Phase 5 will hydrate
    # history from agentcook-storage via session_id.
    messages = [Message(role="user", content=request.message)]

    started_ns = time.perf_counter_ns()
    total_chars = 0
    finish_reason: str | None = None

    try:
        stream_kwargs: dict[str, Any] = {}
        if request.temperature is not None:
            stream_kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            stream_kwargs["max_tokens"] = request.max_tokens

        async for chunk in provider.stream_chat(messages, **stream_kwargs):
            if chunk.delta_content:
                frame = ChatStreamFrame(
                    role="assistant",
                    content=chunk.delta_content,
                    done=False,
                )
                yield f"data: {frame.model_dump_json()}\n\n".encode()
                total_chars += len(chunk.delta_content)
            if chunk.finish_reason:
                finish_reason = chunk.finish_reason
    except Exception as e:
        # SSE-friendly error: terminal frame with error field set.
        error_frame = ChatStreamFrame(
            role="assistant",
            content="",
            done=True,
            error=f"{type(e).__name__}: {str(e)[:200]}",
            metadata={"source": "provider", "model": model_used},
        )
        yield f"data: {error_frame.model_dump_json()}\n\n".encode()
        return

    duration_ms = (time.perf_counter_ns() - started_ns) / 1_000_000

    final_frame = ChatStreamFrame(
        role="assistant",
        content="",
        done=True,
        metadata={
            "model": model_used,
            "provider": provider.__class__.__name__,
            "request_id": uuid.uuid4().hex,
            "duration_ms": round(duration_ms, 1),
            "output_chars": total_chars,
            "finish_reason": finish_reason,
            "source": "provider",
        },
    )
    yield f"data: {final_frame.model_dump_json()}\n\n".encode()


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@router.post(
    "/stream",
    responses={
        200: {
            "description": "SSE stream of chat response frames.",
            "content": {"text/event-stream": {}},
        },
        400: {"description": "Invalid request body."},
    },
    summary="Stream a chat response as Server-Sent Events",
)
async def chat_stream(request: ChatStreamRequest) -> StreamingResponse:
    """Stream an assistant response for the given user message.

    Accepts session_id + message + optional plugin_ids/model override.
    Returns SSE frames: ``data: {"role":"assistant","content":"...","done":false}\\n\\n``
    Final frame has ``done: true`` + metadata (token usage, model, request_id).

    Phase 5: integrates real LLM provider via model_router + hook_runtime
    pre/post hooks + sandbox_runner for tool execution.
    """
    if not request.session_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id must not be empty",
        )

    generator = _stream_mock_response(request) if _use_mock() else _stream_real_response(request)

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
