"""Pydantic v2 schemas for the chat and session endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SESSION_ID_PATTERN = r"^[A-Za-z0-9._:-]{1,128}$"


class ChatStreamRequest(BaseModel):
    """Request body for ``POST /api/v1/chat/stream`` and ``POST /api/v1/chat``."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(
        ...,
        pattern=SESSION_ID_PATTERN,
        description="Conversation id. Created on first use; must belong to the caller.",
    )
    message: str = Field(..., min_length=1, max_length=32_000, description="User message content.")
    agent: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9_-]{0,47}$",
        description="Agent to talk to (see GET /api/v1/agents); defaults to the default agent.",
    )
    plugin_ids: list[str] = Field(
        default_factory=list,
        max_length=16,
        description="Extra toolkit ids to enable for this turn (see GET /api/v1/toolkits).",
    )
    model: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Provider override such as 'qwen:qwen-plus' or 'mock'. Ignored in production."
        ),
    )
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=128_000)


class ToolCallView(BaseModel):
    """A tool call as rendered in the chat UI."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: Literal["running", "success", "error"]
    output: str | None = None
    error: str | None = None
    duration_ms: float | None = None
    turn: int | None = None


FrameType = Literal["start", "delta", "tool_call", "tool_result", "done", "error"]


class ChatStreamFrame(BaseModel):
    """One SSE frame from ``/api/v1/chat/stream`` (documentation model)."""

    model_config = ConfigDict(extra="allow")

    type: FrameType = Field(..., description="Frame kind.")
    role: str = Field(default="assistant", description="v1 field: message role.")
    content: str = Field(default="", description="v1 field: incremental text (delta frames).")
    done: bool = Field(default=False, description="v1 field: true on the terminal frame.")
    session_id: str | None = Field(default=None, description="Echoed on the start frame.")
    run_id: str | None = Field(default=None, description="Run id (start / done / error frames).")
    tool_call: ToolCallView | None = Field(
        default=None, description="tool_call / tool_result frames."
    )
    tool_calls: list[ToolCallView] | None = Field(
        default=None, description="v1 alias of tool_call."
    )
    error: str | None = Field(default=None, description="Error message (error frames).")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Usage, model, timings.")


class ChatResponse(BaseModel):
    """Non-streaming result of ``POST /api/v1/chat``."""

    session_id: str
    run_id: str
    agent: str
    content: str
    tool_calls: list[ToolCallView] = Field(default_factory=list)
    finish_reason: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatCancelResponse(BaseModel):
    run_id: str
    cancelled: bool


class SessionSummary(BaseModel):
    id: str
    title: str
    agent: str
    created_at: str
    updated_at: str
    message_count: int
    active_run_id: str | None = None


class SessionListResponse(BaseModel):
    items: list[SessionSummary]
    total: int


class TranscriptMessage(BaseModel):
    """A transcript entry. Tool results are folded into ``tool_calls`` of
    the assistant message that requested them, matching the live UI."""

    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str | None = None
    tool_calls: list[ToolCallView] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TranscriptResponse(BaseModel):
    session: SessionSummary
    messages: list[TranscriptMessage]


class RenameSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=200)


__all__ = [
    "SESSION_ID_PATTERN",
    "ChatCancelResponse",
    "ChatResponse",
    "ChatStreamFrame",
    "ChatStreamRequest",
    "RenameSessionRequest",
    "SessionListResponse",
    "SessionSummary",
    "ToolCallView",
    "TranscriptMessage",
    "TranscriptResponse",
]
