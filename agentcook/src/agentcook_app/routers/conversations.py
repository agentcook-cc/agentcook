"""Conversation (transcript) endpoints.

- ``GET    /api/v1/conversations``                — the caller's conversations
- ``GET    /api/v1/conversations/{session_id}``   — transcript for the chat UI
- ``PATCH  /api/v1/conversations/{session_id}``   — rename
- ``DELETE /api/v1/conversations/{session_id}``   — delete (cancels an active run)

Named *conversations* (not sessions) to stay clear of agentcook-java's
``/api/v1/sessions`` business aggregate: the Python runtime owns the
transcript; Java owns business-side session records.

The transcript view folds ``tool`` messages into the ``tool_calls`` of
the assistant message that requested them and merges an agent run's
intermediate assistant turns into one bubble — exactly the shape the
live stream produces, so a reloaded conversation looks identical to the
one the user just watched.
"""

from __future__ import annotations

import asyncio
from typing import Any

from agentcook_core import Message
from agentcook_core.conversations import ConversationSummary
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response

from agentcook_app.container import AppContainer, get_container
from agentcook_app.schemas import ErrorEnvelope
from agentcook_app.schemas_chat import (
    SESSION_ID_PATTERN,
    RenameSessionRequest,
    SessionListResponse,
    SessionSummary,
    ToolCallView,
    TranscriptMessage,
    TranscriptResponse,
)
from agentcook_app.security import UserContext, get_current_user

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])

SESSION_PATH = Path(..., pattern=SESSION_ID_PATTERN, description="Conversation id")
_NOT_FOUND = {404: {"model": ErrorEnvelope, "description": "Conversation not found."}}


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail=ErrorEnvelope(
            code="SESSION_NOT_FOUND", message="Conversation not found."
        ).model_dump(),
    )


def _summary(container: AppContainer, s: ConversationSummary) -> SessionSummary:
    active = container.runs.active_for_session(s.session_id)
    return SessionSummary(
        id=s.session_id,
        title=s.title,
        agent=s.agent,
        created_at=s.created_at,
        updated_at=s.updated_at,
        message_count=s.message_count,
        active_run_id=active.run_id if active and active.user_id == s.user_id else None,
    )


def fold_transcript(messages: list[Message]) -> list[TranscriptMessage]:
    """Collapse raw agent-loop messages into chat bubbles."""
    out: list[TranscriptMessage] = []
    current: TranscriptMessage | None = None
    calls_by_id: dict[str, ToolCallView] = {}

    for index, msg in enumerate(messages):
        created = msg.metadata.get("created_at")
        if msg.role == "user":
            current = None
            out.append(
                TranscriptMessage(
                    id=f"m{index}", role="user", content=msg.content, created_at=created
                )
            )
        elif msg.role == "assistant":
            if current is None:
                current = TranscriptMessage(
                    id=f"m{index}", role="assistant", content="", created_at=created
                )
                out.append(current)
            if msg.content:
                current.content = (
                    f"{current.content}\n\n{msg.content}" if current.content else msg.content
                )
            for call in msg.tool_calls or ():
                view = ToolCallView(
                    id=call.id, name=call.name, arguments=call.arguments, status="running"
                )
                calls_by_id[call.id] = view
                current.tool_calls.append(view)
            meta: dict[str, Any] = {
                k: v for k, v in msg.metadata.items() if k not in ("created_at",)
            }
            current.metadata.update(meta)
        elif msg.role == "tool" and msg.tool_call_id in calls_by_id:
            view = calls_by_id[msg.tool_call_id]
            failed = msg.content.startswith("ERROR:")
            view.status = "error" if failed else "success"
            view.output = msg.content
            view.error = msg.content.removeprefix("ERROR:").strip() if failed else None
    return out


@router.get("", response_model=SessionListResponse, summary="List the caller's conversations")
async def list_conversations(
    limit: int = Query(default=50, ge=1, le=200),
    container: AppContainer = Depends(get_container),
    user: UserContext = Depends(get_current_user),
) -> SessionListResponse:
    items = await container.conversations.list_sessions(user.user_id, limit=limit)
    return SessionListResponse(items=[_summary(container, s) for s in items], total=len(items))


@router.get(
    "/{session_id}",
    response_model=TranscriptResponse,
    responses=_NOT_FOUND,
    summary="Get a conversation's transcript",
)
async def get_conversation(
    session_id: str = SESSION_PATH,
    container: AppContainer = Depends(get_container),
    user: UserContext = Depends(get_current_user),
) -> TranscriptResponse:
    summary = await container.conversations.get_session(session_id, user_id=user.user_id)
    if summary is None:
        raise _not_found()
    messages = await container.conversations.load_messages(session_id, user_id=user.user_id)
    return TranscriptResponse(
        session=_summary(container, summary), messages=fold_transcript(messages)
    )


@router.patch(
    "/{session_id}",
    response_model=SessionSummary,
    responses=_NOT_FOUND,
    summary="Rename a conversation",
)
async def rename_conversation(
    body: RenameSessionRequest,
    session_id: str = SESSION_PATH,
    container: AppContainer = Depends(get_container),
    user: UserContext = Depends(get_current_user),
) -> SessionSummary:
    summary = await container.conversations.rename_session(
        session_id, user_id=user.user_id, title=body.title
    )
    if summary is None:
        raise _not_found()
    return _summary(container, summary)


@router.delete(
    "/{session_id}",
    status_code=204,
    responses=_NOT_FOUND,
    summary="Delete a conversation (cancels its active run first)",
)
async def delete_conversation(
    session_id: str = SESSION_PATH,
    container: AppContainer = Depends(get_container),
    user: UserContext = Depends(get_current_user),
) -> Response:
    active = container.runs.active_for_session(session_id)
    if active is not None and active.user_id == user.user_id and active.task is not None:
        container.runs.cancel(active.run_id, user_id=user.user_id)
        # Let the run persist its partial output before the rows go away.
        await asyncio.wait([active.task], timeout=5)
    if not await container.conversations.delete_session(session_id, user_id=user.user_id):
        raise _not_found()
    return Response(status_code=204)


__all__ = ["fold_transcript", "router"]
