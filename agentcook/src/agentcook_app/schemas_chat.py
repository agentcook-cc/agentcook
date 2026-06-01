"""Pydantic v2 schemas for the chat/stream SSE endpoint."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatStreamRequest(BaseModel):
    """Request body for POST /api/v1/chat/stream."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., description="Session to append the message to.")
    message: str = Field(..., min_length=1, max_length=32_000, description="User message content.")
    plugin_ids: list[str] = Field(default_factory=list, description="Plugin IDs to activate for this turn.")
    model: str | None = Field(default=None, description="Override model selection (uses router default if None).")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=128_000)


class ChatStreamFrame(BaseModel):
    """A single SSE frame emitted by the chat/stream endpoint.

    B's useSseChat parses: data: {json}\n\n
    Terminal frame has done=true.
    """

    model_config = ConfigDict(extra="forbid")

    role: str = Field(default="assistant", description="Message role.")
    content: str = Field(default="", description="Incremental content delta.")
    done: bool = Field(default=False, description="True on the final frame.")
    session_id: str | None = Field(default=None, description="Echo session_id on first frame.")
    tool_calls: list[dict[str, Any]] | None = Field(default=None, description="Tool call deltas if any.")
    error: str | None = Field(default=None, description="Error message if stream fails.")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extra metadata (token usage, model, etc.).")
