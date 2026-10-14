"""Delegation graph — ``GET /api/v1/agents/{agent_id}/delegations``.

Nodes are the agent and every agent it can delegate to (from the agent
catalog); edges are the caller's *actual* recent delegations recorded by
the agent loop (``AgentTool`` → ``DelegationLog``), newest last. The
``agent_id`` may be an agent name (``assistant``) or a per-user instance
id (``assistant-<hash>``) — both resolve to the same graph.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from agentcook_app.container import AppContainer, get_container
from agentcook_app.schemas import ErrorEnvelope
from agentcook_app.schemas_delegations import (
    DelegationEdge,
    DelegationGraphResponse,
    DelegationNode,
)
from agentcook_app.security import UserContext, get_current_user

router = APIRouter(prefix="/api/v1/agents", tags=["delegations"])


def _resolve_agent_name(container: AppContainer, agent_id: str) -> str | None:
    if agent_id in container.agents:
        return agent_id
    for spec in container.agents.list():
        if agent_id.startswith(f"{spec.name}-"):
            return spec.name
    return None


@router.get(
    "/{agent_id}/delegations",
    response_model=DelegationGraphResponse,
    responses={404: {"model": ErrorEnvelope, "description": "Agent not found"}},
    summary="Delegation graph for one agent (catalog topology + recent delegations)",
)
async def get_delegations(
    agent_id: str = Path(..., pattern=r"^[A-Za-z0-9_\-]{1,64}$"),
    limit: int = Query(default=50, ge=1, le=500),
    container: AppContainer = Depends(get_container),
    user: UserContext = Depends(get_current_user),
) -> DelegationGraphResponse:
    name = _resolve_agent_name(container, agent_id)
    if name is None:
        raise HTTPException(
            status_code=404,
            detail=ErrorEnvelope(
                code="AGENT_NOT_FOUND", message=f"Agent {agent_id!r} not found."
            ).model_dump(),
        )
    root = container.agents.get(name)
    assert root is not None
    participant_names = [root.name, *root.delegates]
    events = container.delegations.for_agent(root.name, user_id=user.user_id, limit=limit)
    for event in events:
        for key in ("from", "to"):
            if event.get(key) and event[key] not in participant_names:
                participant_names.append(event[key])

    nodes = []
    for participant in participant_names:
        spec = container.agents.get(participant)
        nodes.append(
            DelegationNode(
                id=participant,
                name=spec.title if spec else participant,
                role="orchestrator"
                if participant == root.name
                else (spec.description[:80] if spec else "agent"),
            )
        )
    edges = [
        DelegationEdge(
            id=str(event.get("run_id") or index),
            from_id=str(event.get("from")),
            to_id=str(event.get("to")),
            task=str(event.get("task", ""))[:200],
            status="succeeded" if event.get("success") else "failed",
            started_at=str(event.get("started_at", "")),
            completed_at=event.get("completed_at"),
        )
        for index, event in enumerate(events)
    ]
    return DelegationGraphResponse(agent_id=agent_id, nodes=nodes, edges=edges)


__all__ = ["router"]
