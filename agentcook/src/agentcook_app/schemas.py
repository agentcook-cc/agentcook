"""Pydantic v2 schemas for the agentcook Memory API surface.

Mirrors ``agent-a-day-11-memory-api-for-b.md``. Wire format follows the
canonical error envelope from `frontend-conventions.md §7.6`:

    {"code": "ERROR_CODE", "message": "human readable", "detail": {...}}

(flat, *not* nested under ``error``). This was Day 11 doc drift —
B's section 7.6 is the consumer-driven baseline so we align to it.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MemoryEventKindLit = Literal[
    "observation", "decision", "tool_use", "user_input", "reflection"
]


# --------------------------------------------------------------------------
# Error envelope (all endpoints)
# --------------------------------------------------------------------------


class ErrorEnvelope(BaseModel):
    """Flat error shape — matches frontend-conventions §7.6 (B canonical)."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="Machine-readable error code (UPPER_SNAKE).")
    message: str = Field(..., description="Human-readable description.")
    detail: dict[str, Any] | None = Field(
        default=None, description="Optional structured context."
    )


# --------------------------------------------------------------------------
# Identity (read-only — ADR-011 layer 1, immutable)
# --------------------------------------------------------------------------


class IdentityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    role: str
    created_at: str = Field(..., description="ISO-8601 UTC timestamp")
    scopes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------
# Soul (read + replace — ADR-011 layer 2, append-only versioning)
# --------------------------------------------------------------------------


class SoulConfigBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tone: str = "neutral"
    language_style: str = "concise"
    values: list[str] = Field(default_factory=list)
    custom_traits: dict[str, str] = Field(default_factory=dict)


class SoulResponse(SoulConfigBody):
    """Returned with the persisted version (echoes input on POST)."""


class SoulVersionResponse(BaseModel):
    """A single point in the per-agent soul history."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(..., ge=1)
    created_at: str
    config: SoulConfigBody


class SoulHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SoulVersionResponse] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Memory events (list / delete — ADR-011 layer 3 event stream)
# --------------------------------------------------------------------------


class MemoryEventCreate(BaseModel):
    """Body for ``POST /agents/{id}/memory/events``.

    Server assigns ``id`` and (if omitted) ``timestamp``.
    """

    model_config = ConfigDict(extra="forbid")

    kind: MemoryEventKindLit
    content: str = Field(..., min_length=1, max_length=16_384)
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: str | None = Field(
        default=None,
        description="ISO-8601 UTC. If omitted, server sets it at write time.",
    )


class MemoryEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="String id to avoid enumeration attacks.")
    timestamp: str
    kind: MemoryEventKindLit
    content: str
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryEventListResponse(BaseModel):
    """Cursor-pagination response.

    Note: per `frontend-conventions §7.6` constraint #5 list endpoints
    should expose ``{items, total, page, size}``. Memory event listing
    intentionally uses **cursor pagination** instead (event streams are
    append-only — page/size becomes unstable as new events arrive).
    Documented exception; flagged in §7 increment to B.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[MemoryEventResponse] = Field(default_factory=list)
    next_cursor: str | None = None


# --------------------------------------------------------------------------
# Search (semantic recall — v1 cosine, hybrid BM25 fusion Day 22)
# --------------------------------------------------------------------------


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=1024)
    top_k: int = Field(default=5, ge=1, le=50)


class MemoryHitResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    score: float = Field(..., ge=0.0, le=1.0)
    event: MemoryEventResponse | None = None


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    hits: list[MemoryHitResponse] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Flush (destructive, double-confirm)
# --------------------------------------------------------------------------


class FlushRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: Literal[
        "I understand this deletes all events for this agent."
    ] = Field(..., description="Exact string required to prevent accidental flush.")
    preserve_identity_and_soul: bool = True


class FlushResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted_event_count: int
    identity_preserved: bool
    soul_preserved: bool


__all__ = [
    "ErrorEnvelope",
    "FlushRequest",
    "FlushResponse",
    "IdentityResponse",
    "MemoryEventCreate",
    "MemoryEventKindLit",
    "MemoryEventListResponse",
    "MemoryEventResponse",
    "MemoryHitResponse",
    "SearchRequest",
    "SearchResponse",
    "SoulConfigBody",
    "SoulHistoryResponse",
    "SoulResponse",
    "SoulVersionResponse",
]
