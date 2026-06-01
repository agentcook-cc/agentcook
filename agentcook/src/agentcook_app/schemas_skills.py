"""Pydantic schemas for the Skills API (Day 27 scaffolding).

Kept in a separate module from ``schemas.py`` so the Day 28 spec bump
shows a clean diff: when ``main.py`` starts including the router and
the freeze metadata moves to 1.1.0, only this file + ``routers/skills.py``
participate in the change. ``schemas.py`` (Memory/Soul/Identity) stays
untouched.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SkillSummary(BaseModel):
    """One row in ``GET /api/v1/skills`` — what B's SkillListView shows."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Stable skill identifier (kebab-case).")
    name: str = Field(..., description="Display name.")
    description: str = Field(..., description="One-line summary.")
    version: str = Field(..., description="Semver string from the skill manifest.")
    category: str = Field(..., description="Loose grouping (memory / nlp / chat / ...).")
    updated_at: str = Field(..., description="ISO-8601 UTC timestamp of last edit.")


class SkillListResponse(BaseModel):
    """Envelope for the skill list endpoint."""

    model_config = ConfigDict(extra="forbid")

    items: list[SkillSummary] = Field(..., description="Skills, ordered as the registry yields them.")
    total: int = Field(..., description="Total count — equals ``len(items)`` until pagination lands.")


class SkillDetailResponse(SkillSummary):
    """``GET /api/v1/skills/{id}`` — adds the skill body (markdown + frontmatter)."""

    model_config = ConfigDict(extra="forbid")

    body: str = Field(..., description="Raw skill body (markdown). Empty for placeholder skills.")


class SkillTestRequest(BaseModel):
    """Body for ``POST /api/v1/skills/{id}/test/stream``.

    The ``input`` is whatever the SkillTestDialog's textarea contains;
    structured ``args`` may be added later (Phase 5 once real skill
    schemas are loaded). Today the SSE mock ignores ``args`` and just
    echoes ``input`` back through the streamed chunks.
    """

    model_config = ConfigDict(extra="forbid")

    input: str = Field(..., description="Free-form test input the skill will receive.")
    args: dict | None = Field(default=None, description="Optional structured args (Phase 5).")


__all__ = [
    "SkillDetailResponse",
    "SkillListResponse",
    "SkillSummary",
    "SkillTestRequest",
]
