"""Chat endpoints — the agent loop over HTTP.

- ``POST /api/v1/chat/stream`` — run one agent turn, stream frames (SSE).
- ``POST /api/v1/chat``        — same turn, single JSON response.
- ``POST /api/v1/chat/runs/{run_id}/cancel`` — stop a running turn.

Wire format (one JSON object per ``data:`` line)::

    {"type":"start",       "session_id", "run_id", "metadata":{agent, model, …}}
    {"type":"delta",       "content":"partial text"}
    {"type":"tool_call",   "tool_call":{"id","name","arguments","status":"running"}}
    {"type":"tool_result", "tool_call":{…, "status":"success|error","output","duration_ms"}}
    {"type":"done",        "done":true, "metadata":{usage, model, turns, finish_reason, …}}
    {"type":"error",       "done":true, "error":"…"}

Every frame also carries the v1 fields ``role`` / ``content`` / ``done``,
so v1 clients that only concatenate ``content`` keep working. Comment
lines (``: ping``) are sent every 15s during long tool calls to keep
proxies from closing the connection.

The run itself is owned by the run manager, not by this response: a
client disconnect does not abort it and its result is still persisted.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from agentcook_core.conversations import SessionAccessError
from fastapi import APIRouter, Depends, Header, HTTPException, Path, status
from fastapi.responses import StreamingResponse

from agentcook_app.chat_service import (
    AgentNotAvailableError,
    ChatService,
    ChatTurn,
    ModelUnavailableError,
)
from agentcook_app.container import AppContainer, StorageNotReadyError, get_container
from agentcook_app.middleware.turnstile import get_turnstile_verifier
from agentcook_app.runs import RunHandle, SessionBusyError
from agentcook_app.schemas import ErrorEnvelope
from agentcook_app.schemas_chat import (
    ChatCancelResponse,
    ChatResponse,
    ChatStreamRequest,
    ToolCallView,
)
from agentcook_app.security import UserContext, get_current_user

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def _error(status_code: int, code: str, message: str, detail: Any = None) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=ErrorEnvelope(code=code, message=message, detail=detail).model_dump(),
    )


async def _check_turnstile(
    container: AppContainer, token: str | None, forwarded_for: str | None
) -> None:
    settings = container.settings
    if not settings.turnstile_enforce or settings.uses_mock_model:
        return
    remote_ip = forwarded_for.split(",")[0].strip() if forwarded_for else None
    decision = await get_turnstile_verifier().verify(token, remote_ip=remote_ip)
    if not decision.verified:
        raise _error(
            status.HTTP_401_UNAUTHORIZED,
            "TURNSTILE_REJECTED",
            f"Turnstile verification failed: {decision.reason}",
            {"reason": decision.reason, "error_codes": list(decision.error_codes)},
        )


async def _start(container: AppContainer, user: UserContext, body: ChatStreamRequest) -> RunHandle:
    turn = ChatTurn(
        session_id=body.session_id,
        message=body.message,
        agent=body.agent,
        plugin_ids=tuple(body.plugin_ids),
        model=body.model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
    )
    try:
        return await ChatService(container).start_turn(user, turn)
    except AgentNotAvailableError as exc:
        raise _error(404, "AGENT_NOT_FOUND", str(exc), {"available": exc.available}) from exc
    except SessionAccessError as exc:
        # Same response as "missing" so session ids can't be probed.
        raise _error(404, "SESSION_NOT_FOUND", "Session not found.") from exc
    except SessionBusyError as exc:
        raise _error(
            409,
            "SESSION_BUSY",
            "This session is already generating a reply; wait for it or cancel it.",
            {"run_id": exc.run_id},
        ) from exc
    except ModelUnavailableError as exc:
        if exc.client_error:
            raise _error(400, "INVALID_MODEL", str(exc), {"model": exc.spec}) from exc
        raise _error(503, "MODEL_UNAVAILABLE", str(exc), {"model": exc.spec}) from exc
    except StorageNotReadyError as exc:
        raise _error(503, "STORAGE_NOT_READY", str(exc)) from exc


async def _sse(handle: RunHandle) -> AsyncIterator[bytes]:
    async for frame in handle.frames():
        if frame is None:
            yield b": ping\n\n"
            continue
        yield f"data: {json.dumps(frame, ensure_ascii=False, default=str)}\n\n".encode()


@router.post(
    "/stream",
    responses={
        200: {"description": "SSE stream of chat frames.", "content": {"text/event-stream": {}}},
        401: {
            "model": ErrorEnvelope,
            "description": "Missing/invalid token or Turnstile rejection.",
        },
        404: {"model": ErrorEnvelope, "description": "Unknown agent or session."},
        409: {"model": ErrorEnvelope, "description": "Session already has an active run."},
        422: {"model": ErrorEnvelope, "description": "Invalid request body."},
    },
    summary="Run one agent turn and stream it as Server-Sent Events",
)
async def chat_stream(
    body: ChatStreamRequest,
    container: AppContainer = Depends(get_container),
    user: UserContext = Depends(get_current_user),
    x_turnstile_token: str | None = Header(default=None, alias="X-Turnstile-Token"),
    x_forwarded_for: str | None = Header(default=None, alias="X-Forwarded-For"),
) -> StreamingResponse:
    await _check_turnstile(container, x_turnstile_token, x_forwarded_for)
    handle = await _start(container, user, body)
    return StreamingResponse(_sse(handle), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post(
    "",
    response_model=ChatResponse,
    responses={
        401: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
        409: {"model": ErrorEnvelope},
    },
    summary="Run one agent turn and return the complete answer",
)
async def chat(
    body: ChatStreamRequest,
    container: AppContainer = Depends(get_container),
    user: UserContext = Depends(get_current_user),
    x_turnstile_token: str | None = Header(default=None, alias="X-Turnstile-Token"),
    x_forwarded_for: str | None = Header(default=None, alias="X-Forwarded-For"),
) -> ChatResponse:
    await _check_turnstile(container, x_turnstile_token, x_forwarded_for)
    handle = await _start(container, user, body)
    content: list[str] = []
    tools: dict[str, ToolCallView] = {}
    final: dict[str, Any] = {}
    async for frame in handle.frames():
        if frame is None:
            continue
        kind = frame.get("type")
        if kind == "delta":
            content.append(frame["content"])
        elif kind in ("tool_call", "tool_result"):
            call = frame["tool_call"]
            tools[call["id"]] = ToolCallView(**call)
        elif kind in ("done", "error"):
            final = frame
    metadata = final.get("metadata", {})
    return ChatResponse(
        session_id=body.session_id,
        run_id=final.get("run_id", handle.run_id),
        agent=handle.agent,
        content="".join(content),
        tool_calls=list(tools.values()),
        finish_reason=metadata.get("finish_reason") or ("error" if final.get("error") else None),
        error=final.get("error"),
        metadata=metadata,
    )


@router.post(
    "/runs/{run_id}/cancel",
    response_model=ChatCancelResponse,
    responses={404: {"model": ErrorEnvelope, "description": "No active run with this id."}},
    summary="Stop an in-flight agent run (the UI's Stop button)",
)
async def cancel_run(
    run_id: str = Path(..., pattern=r"^run_[a-f0-9]{16}$"),
    container: AppContainer = Depends(get_container),
    user: UserContext = Depends(get_current_user),
) -> ChatCancelResponse:
    if not container.runs.cancel(run_id, user_id=user.user_id):
        raise _error(404, "RUN_NOT_FOUND", "No active run with this id.")
    return ChatCancelResponse(run_id=run_id, cancelled=True)


__all__ = ["router"]
