"""Pydantic schemas for the Logs streaming API (Day 30 scaffolding).

The ``LogFrame`` shape mirrors structlog's per-line dict (the
``logging_config.configure()`` setup already emits these fields). When
Phase 5 wires the SSE endpoint to a real broadcast handler, the same
frame type flows through unchanged — B's LogStreamView and the live
log emitter share one contract.

Kept in a separate module from ``schemas.py`` so the Day 31 spec bump
shows a clean diff (same hygiene rule used for ``schemas_skills.py``
on Day 27→28 and ``schemas_delegations.py`` on Day 29).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


LogLevel = Literal["debug", "info", "warning", "error", "critical"]


class LogFrame(BaseModel):
    """One streamed log line — matches structlog's per-line shape."""

    model_config = ConfigDict(extra="forbid")

    timestamp: str = Field(..., description="ISO-8601 UTC timestamp.")
    level: LogLevel = Field(..., description="Log severity level.")
    event: str = Field(..., description="Short human-readable event name.")
    request_id: str | None = Field(default=None, description="Per-request correlation id (hex).")
    logger: str | None = Field(default=None, description="Logger name (e.g. ``agentcook_app.main``).")
    extra: dict[str, Any] = Field(default_factory=dict, description="Free-form structured fields.")


__all__ = [
    "LogFrame",
    "LogLevel",
]
