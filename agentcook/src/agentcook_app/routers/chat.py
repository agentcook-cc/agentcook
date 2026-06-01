"""Chat streaming endpoint — Day 34 收官 (Phase 3 Day 9).

Implements ``POST /api/v1/chat/stream`` — the primary SSE endpoint for
B's ``useSseChat`` hook. Accepts a user message + optional plugin/model
config, streams assistant response frames.

Integration points:
- ``model_router``: selects LLM model based on policy/availability
- ``hook_runtime``: fires pre/post hooks (logging, metrics, plugins)
- ``sandbox_runner``: executes plugin code if tool calls require it

Phase 5 replaces the mock LLM with real provider calls. Today's mock
generates a realistic multi-frame streaming response for B to develop
against.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from agentcook_app.schemas_chat import ChatStreamFrame, ChatStreamRequest

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


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

    return StreamingResponse(
        _stream_mock_response(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
