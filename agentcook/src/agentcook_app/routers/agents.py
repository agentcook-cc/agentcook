"""Agent catalog + runtime introspection.

- ``GET /api/v1/agents``          — agents the caller can chat with
- ``GET /api/v1/agents/{name}``   — one agent: spec, effective tools, skills
- ``GET /api/v1/toolkits``        — executable toolkits (``plugin_ids`` values)
- ``GET /api/v1/runtime``         — non-secret runtime configuration summary

Each agent entry carries the caller's ``instance_id`` — the id under
which that user's identity / soul / long-term memory for this agent is
stored (use it with the ``/api/v1/agents/{agent_id}/memory`` endpoints).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from agentcook_app.chat_service import agent_instance_id
from agentcook_app.container import AppContainer, get_container
from agentcook_app.schemas import ErrorEnvelope
from agentcook_app.security import UserContext, get_current_user

router = APIRouter(prefix="/api/v1", tags=["agents"])


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class AgentInfo(BaseModel):
    name: str
    title: str
    description: str
    default: bool
    toolkits: list[str]
    skills: list[str]
    memory: bool
    delegates: list[str]
    instance_id: str


class AgentDetail(AgentInfo):
    instructions: str
    max_turns: int
    tools: list[ToolInfo]


class AgentListResponse(BaseModel):
    items: list[AgentInfo]
    default_agent: str


class ToolkitInfo(BaseModel):
    id: str
    name: str
    description: str
    tools: list[ToolInfo]


class ToolkitListResponse(BaseModel):
    items: list[ToolkitInfo]


def _skill_names(container: AppContainer, skills: tuple[str, ...] | None) -> list[str]:
    if skills is None:
        return sorted(e.manifest.name for e in container.skills.list_skills())
    return [s for s in skills if s in container.skills]


def _info(container: AppContainer, spec: Any, user: UserContext) -> dict[str, Any]:
    return {
        "name": spec.name,
        "title": spec.title,
        "description": spec.description,
        "default": spec.name == container.agents.default,
        "toolkits": list(spec.toolkits),
        "skills": _skill_names(container, spec.skills),
        "memory": spec.memory,
        "delegates": list(spec.delegates),
        "instance_id": agent_instance_id(spec.name, user.user_id),
    }


@router.get("/agents", response_model=AgentListResponse, summary="List available agents")
async def list_agents(
    container: AppContainer = Depends(get_container),
    user: UserContext = Depends(get_current_user),
) -> AgentListResponse:
    return AgentListResponse(
        items=[AgentInfo(**_info(container, s, user)) for s in container.agents.list()],
        default_agent=container.agents.default,
    )


@router.get(
    "/agents/{name}",
    response_model=AgentDetail,
    responses={404: {"model": ErrorEnvelope}},
    summary="Describe one agent, including its effective tool list",
)
async def get_agent(
    name: str = Path(..., pattern=r"^[a-z][a-z0-9_-]{0,47}$"),
    container: AppContainer = Depends(get_container),
    user: UserContext = Depends(get_current_user),
) -> AgentDetail:
    spec = container.agents.get(name)
    if spec is None or spec.name != name:
        raise HTTPException(
            status_code=404,
            detail=ErrorEnvelope(
                code="AGENT_NOT_FOUND", message=f"Agent {name!r} not found."
            ).model_dump(),
        )
    tools, _ = container.toolkits.resolve(spec.toolkits)
    tool_infos = [
        ToolInfo(name=t.name, description=t.description, parameters=t.parameters_schema)
        for t in tools
    ]
    if spec.memory:
        tool_infos += [
            ToolInfo(name="remember", description="Save a durable fact to long-term memory."),
            ToolInfo(name="recall", description="Search long-term memory."),
        ]
    if _skill_names(container, spec.skills):
        tool_infos.append(ToolInfo(name="load_skill", description="Load a skill's instructions."))
    for delegate in spec.delegates:
        tool_infos.append(
            ToolInfo(name=f"delegate_to_{delegate}", description=f"Delegate a task to {delegate}.")
        )
    return AgentDetail(
        **_info(container, spec, user),
        instructions=spec.instructions,
        max_turns=spec.max_turns or container.settings.max_turns,
        tools=tool_infos,
    )


@router.get("/toolkits", response_model=ToolkitListResponse, summary="List executable toolkits")
async def list_toolkits(container: AppContainer = Depends(get_container)) -> ToolkitListResponse:
    return ToolkitListResponse(
        items=[ToolkitInfo(**kit.describe()) for kit in container.toolkits.list()]
    )


@router.get("/runtime", summary="Runtime configuration summary (no secrets)")
async def runtime_info(container: AppContainer = Depends(get_container)) -> dict[str, Any]:
    return {**container.describe(), "active_runs": container.runs.active_count}


__all__ = ["router"]
