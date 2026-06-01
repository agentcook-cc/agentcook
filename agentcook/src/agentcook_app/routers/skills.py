"""Skills API endpoints — Day 27 skeleton (Phase 3 Day 2).

**Status**: scaffolding only. This router is **not yet included** in
``agentcook_app.main.create_app`` — including it would change the live
OpenAPI spec and require bumping ``v1.yaml`` to 1.1.0 (per the change
policy in ``docs/api/CHANGELOG.md``). Day 28 will:

1. Wire it into ``main.py`` via ``app.include_router(skills.router)``.
2. Bump ``info.version`` to ``1.1.0``.
3. Re-run ``scripts/dump-openapi.py``.
4. Notify B (regenerate types) + C (re-run Pact provider verify).
5. Append a row to ``docs/api/CHANGELOG.md``.

What ships today:

- ``GET /api/v1/skills`` — list available skill manifests
- ``GET /api/v1/skills/{skill_id}`` — fetch a single skill's metadata + body

Both back onto an in-memory mock today. A real ``SkillRegistry``
backend (from ``agentcook_core.skill_loader``) lands when B's
``SkillTestDialog`` needs streamed execution on Day 28 — at that point
the SSE ``POST /api/v1/skills/{id}/test/stream`` endpoint joins the
router and the registry dependency is wired through.

Pagination / search / category-filter are intentionally absent today —
B's Day 28 ``SkillListView`` shows < 100 items and pagination is a
Phase 4+ concern. Add when needed, not before.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Path, status
from fastapi.responses import StreamingResponse

from agentcook_app.schemas_skills import (
    SkillDetailResponse,
    SkillListResponse,
    SkillSummary,
    SkillTestRequest,
)

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


# --------------------------------------------------------------------------
# Mock fixture — replaced by SkillRegistry dependency on Day 28
# --------------------------------------------------------------------------


def _mock_skills() -> list[dict]:
    """Five demo skills with the shape B's UI will see.

    Names mirror the canonical skill bundles in ``tutorial/companion-repos``
    so B's Day 28 design can preview real-looking data. The body is a
    placeholder until ``SkillRegistry.load_skill_file`` is wired in.
    """
    now = dt.datetime(2026, 6, 3, 9, 0, 0, tzinfo=dt.UTC).isoformat()
    return [
        {
            "id": "summarize-conversation",
            "name": "Summarize Conversation",
            "description": "Condense a long chat into key bullet points.",
            "version": "1.0.0",
            "category": "memory",
            "updated_at": now,
        },
        {
            "id": "extract-entities",
            "name": "Extract Entities",
            "description": "Pull named entities (people, places, products) from text.",
            "version": "0.3.1",
            "category": "nlp",
            "updated_at": now,
        },
        {
            "id": "classify-intent",
            "name": "Classify Intent",
            "description": "Map a user utterance to one of a registered intent set.",
            "version": "1.2.0",
            "category": "nlp",
            "updated_at": now,
        },
        {
            "id": "generate-followups",
            "name": "Generate Follow-ups",
            "description": "Suggest 3 follow-up questions for the current conversation.",
            "version": "0.1.0",
            "category": "chat",
            "updated_at": now,
        },
        {
            "id": "translate-text",
            "name": "Translate Text",
            "description": "Translate text between supported languages.",
            "version": "2.0.0",
            "category": "nlp",
            "updated_at": now,
        },
    ]


_SKILLS_INDEX: dict[str, dict] = {s["id"]: s for s in _mock_skills()}


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@router.get(
    "",
    response_model=SkillListResponse,
    summary="List available skills",
)
async def list_skills() -> SkillListResponse:
    """Return all registered skills (no pagination today — B's Day 28
    view caps at < 100 items; revisit when that no longer holds)."""
    summaries = [SkillSummary(**s) for s in _SKILLS_INDEX.values()]
    return SkillListResponse(items=summaries, total=len(summaries))


@router.get(
    "/{skill_id}",
    response_model=SkillDetailResponse,
    responses={404: {"description": "Skill not found"}},
    summary="Fetch a single skill's manifest + body",
)
async def get_skill(
    skill_id: str = Path(..., description="Skill identifier", pattern=r"^[a-z0-9-]+$"),
) -> SkillDetailResponse:
    entry = _SKILLS_INDEX.get(skill_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill {skill_id!r} not found",
        )
    # Mock body — Day 28 wires the real SkillEntry.load_body() through.
    body_placeholder = (
        f"# {entry['name']}\n\n"
        f"{entry['description']}\n\n"
        "<!-- skill body placeholder; real load lands Day 28 -->\n"
    )
    return SkillDetailResponse(
        **entry,
        body=body_placeholder,
    )


# --------------------------------------------------------------------------
# SSE: POST /api/v1/skills/{id}/test/stream
# --------------------------------------------------------------------------


_SSE_CHUNK_COUNT = 10
_SSE_CHUNK_INTERVAL_SECS = 0.5


async def _mock_skill_stream(skill_id: str, payload: SkillTestRequest) -> AsyncIterator[bytes]:
    """Yield ``_SSE_CHUNK_COUNT`` SSE frames pacing roughly every 500ms.

    Phase 5 will replace this with ``SkillRegistry.load_skill_file(...).execute(...)``
    streamed through the real LLM provider. Today's mock exists so B's
    ``SkillTestDialog`` + ``useSseChat`` hook can be wired end-to-end
    against the live spec.

    Wire format: ``data: {json}\\n\\n`` — the SSE default ``data`` event.
    Each frame carries ``{"chunk_index", "total", "delta", "finished"}``.
    """
    echo = payload.input or "(empty input)"
    for i in range(_SSE_CHUNK_COUNT):
        finished = i == _SSE_CHUNK_COUNT - 1
        frame = {
            "chunk_index": i,
            "total": _SSE_CHUNK_COUNT,
            "delta": f"[skill={skill_id}] tick {i + 1}/{_SSE_CHUNK_COUNT}: {echo[: 32]}",
            "finished": finished,
        }
        yield f"data: {json.dumps(frame, ensure_ascii=False)}\n\n".encode()
        if not finished:
            await asyncio.sleep(_SSE_CHUNK_INTERVAL_SECS)


@router.post(
    "/{skill_id}/test/stream",
    responses={
        200: {
            "description": "SSE stream of skill execution chunks.",
            "content": {"text/event-stream": {}},
        },
        404: {"description": "Skill not found"},
    },
    summary="Execute a skill with test input and stream the result via SSE",
)
async def test_skill_stream(
    payload: SkillTestRequest,
    skill_id: str = Path(..., description="Skill identifier", pattern=r"^[a-z0-9-]+$"),
) -> StreamingResponse:
    if skill_id not in _SKILLS_INDEX:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill {skill_id!r} not found",
        )
    return StreamingResponse(
        _mock_skill_stream(skill_id, payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering for SSE
        },
    )
