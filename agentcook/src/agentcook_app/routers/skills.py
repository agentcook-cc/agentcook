"""Skills API — backed by the live :class:`SkillRegistry`.

- ``GET  /api/v1/skills``                  — catalog (bundled + ``AGENTCOOK_SKILLS_DIRS``)
- ``GET  /api/v1/skills/{skill_id}``       — manifest + markdown body
- ``POST /api/v1/skills/{skill_id}/test/stream`` — run the skill once (SSE)

A skill test runs a throw-away agent whose instructions *are* the skill
body, with the core + commerce-demo toolkits available, against the
configured model. Nothing is persisted. Frames keep the v1 shape the
admin ``SkillTestDialog`` reads (``chunk_index`` / ``delta`` /
``finished``) and add ``type`` plus tool-call detail.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import AsyncIterator
from typing import Any

from agentcook_core import (
    Agent,
    AgentRunner,
    RunCompleted,
    RunFailed,
    TextDelta,
    ToolCallCompleted,
    ToolCallStarted,
)
from agentcook_core.prompts import build_agent_system_prompt
from agentcook_core.skill_loader import SkillEntry
from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import StreamingResponse

from agentcook_app.container import AppContainer, get_container
from agentcook_app.schemas import ErrorEnvelope
from agentcook_app.schemas_skills import (
    SkillDetailResponse,
    SkillListResponse,
    SkillSummary,
    SkillTestRequest,
)
from agentcook_app.security import UserContext, get_current_user

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])

SKILL_ID_PATH = Path(..., description="Skill identifier", pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")


def _summary(entry: SkillEntry) -> SkillSummary:
    m = entry.manifest
    updated = m.updated_at
    if not updated:
        mtime = entry._path.stat().st_mtime  # noqa: SLF001 — SkillEntry exposes no public path
        updated = dt.datetime.fromtimestamp(mtime, tz=dt.UTC).isoformat(timespec="seconds")
    return SkillSummary(
        id=m.name,
        name=m.title or m.name.replace("-", " ").title(),
        description=m.description,
        version=m.version,
        category=m.category or "general",
        updated_at=updated,
    )


def _get_entry(container: AppContainer, skill_id: str) -> SkillEntry:
    entry = container.skills.get(skill_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorEnvelope(
                code="SKILL_NOT_FOUND", message=f"Skill {skill_id!r} not found."
            ).model_dump(),
        )
    return entry


@router.get("", response_model=SkillListResponse, summary="List available skills")
async def list_skills(container: AppContainer = Depends(get_container)) -> SkillListResponse:
    summaries = [_summary(e) for e in container.skills.list_skills()]
    summaries.sort(key=lambda s: (s.category, s.id))
    return SkillListResponse(items=summaries, total=len(summaries))


@router.get(
    "/{skill_id}",
    response_model=SkillDetailResponse,
    responses={404: {"model": ErrorEnvelope, "description": "Skill not found"}},
    summary="Fetch a single skill's manifest + body",
)
async def get_skill(
    skill_id: str = SKILL_ID_PATH,
    container: AppContainer = Depends(get_container),
) -> SkillDetailResponse:
    entry = _get_entry(container, skill_id)
    return SkillDetailResponse(**_summary(entry).model_dump(), body=entry.load())


async def _skill_stream(
    container: AppContainer, entry: SkillEntry, payload: SkillTestRequest
) -> AsyncIterator[bytes]:
    tools, _ = container.toolkits.resolve(["core", "commerce-demo"])
    agent = Agent(
        name="skill-tester",
        instructions=build_agent_system_prompt(
            instructions=(
                f"You are testing the skill '{entry.manifest.name}'. Apply the skill "
                f"below to the user's input.\n\n{entry.load()}"
            )
        ),
        tools=tuple(tools),
        max_turns=min(6, container.settings.max_turns),
        tool_timeout=container.settings.tool_timeout,
        max_tokens=(payload.args or {}).get("max_tokens")
        if isinstance(payload.args, dict)
        else None,
    )
    runner = AgentRunner(container.provider_for(None))
    index = 0

    def frame(**fields: Any) -> bytes:
        nonlocal index
        body = {"chunk_index": index, "total": None, "finished": False, "delta": "", **fields}
        index += 1
        return f"data: {json.dumps(body, ensure_ascii=False, default=str)}\n\n".encode()

    async for event in runner.run_stream(agent, payload.input or "(empty input)"):
        if isinstance(event, TextDelta):
            yield frame(type="delta", delta=event.text)
        elif isinstance(event, ToolCallStarted):
            yield frame(
                type="tool_call",
                tool_call={
                    "id": event.call.id,
                    "name": event.call.name,
                    "arguments": event.call.arguments,
                },
            )
        elif isinstance(event, ToolCallCompleted):
            yield frame(
                type="tool_result",
                tool_call={
                    "id": event.call.id,
                    "name": event.call.name,
                    "status": "success" if event.result.success else "error",
                    "output": event.output[:2_000],
                },
            )
        elif isinstance(event, RunCompleted):
            yield frame(
                type="done",
                finished=True,
                metadata={
                    "skill": entry.manifest.name,
                    "turns": event.turns,
                    "usage": {
                        "input_tokens": event.usage.input,
                        "output_tokens": event.usage.output,
                    },
                    "duration_ms": round(event.duration_ms, 1),
                },
            )
        elif isinstance(event, RunFailed):
            yield frame(type="error", finished=True, error=f"{event.error_type}: {event.error}")


@router.post(
    "/{skill_id}/test/stream",
    responses={
        200: {
            "description": "SSE stream of skill execution chunks.",
            "content": {"text/event-stream": {}},
        },
        404: {"model": ErrorEnvelope, "description": "Skill not found"},
    },
    summary="Execute a skill with test input and stream the result via SSE",
)
async def test_skill_stream(
    payload: SkillTestRequest,
    skill_id: str = SKILL_ID_PATH,
    container: AppContainer = Depends(get_container),
    user: UserContext = Depends(get_current_user),
) -> StreamingResponse:
    entry = _get_entry(container, skill_id)
    return StreamingResponse(
        _skill_stream(container, entry, payload),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


__all__ = ["router"]
