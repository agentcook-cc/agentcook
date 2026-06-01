"""Delegations API endpoint — Day 29 skeleton (Phase 3 Day 4).

**Status**: scaffolding only. **Not wired** into ``main.py`` yet —
including it would push ``v1.yaml`` past the v1.1.0 freeze without an
accompanying minor bump. Day 31 wires it in alongside the
``GET /api/v1/agents/{id}/delegations`` endpoint B's reactflow
visualization needs.

Day 31 v1.2.0 bump covers BOTH this router AND ``routers/logs.py``
(scaffolded Day 30) — see ``routers/logs.py`` docstring for the full
7-step SOP. One bump, two endpoints — keeps B's regen / C's Pact
reverify cadence at one cycle per Phase 3 day.

Today's mock returns 3 nodes + 2 edges that look plausible for B's
reactflow design preview. Phase 5 swaps the body to a live
``MultiAgentOrchestrator`` snapshot.
"""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException, Path, status

from agentcook_app.schemas_delegations import (
    DelegationEdge,
    DelegationGraphResponse,
    DelegationNode,
)

router = APIRouter(prefix="/api/v1/agents", tags=["delegations"])


# --------------------------------------------------------------------------
# Mock fixture — replaced by MultiAgentOrchestrator snapshot in Phase 5
# --------------------------------------------------------------------------


def _mock_graph(agent_id: str) -> DelegationGraphResponse:
    """Three-agent demo graph: planner delegates to coder + reviewer."""
    started = dt.datetime(2026, 6, 5, 9, 0, 0, tzinfo=dt.UTC).isoformat()
    completed = dt.datetime(2026, 6, 5, 9, 0, 30, tzinfo=dt.UTC).isoformat()
    return DelegationGraphResponse(
        agent_id=agent_id,
        nodes=[
            DelegationNode(id="planner", name="Planner", role="planner"),
            DelegationNode(id="coder", name="Coder", role="coder"),
            DelegationNode(id="reviewer", name="Reviewer", role="reviewer"),
        ],
        edges=[
            DelegationEdge(
                id="e1",
                from_id="planner",
                to_id="coder",
                task="Implement the search endpoint",
                status="succeeded",
                started_at=started,
                completed_at=completed,
            ),
            DelegationEdge(
                id="e2",
                from_id="planner",
                to_id="reviewer",
                task="Review the search endpoint diff",
                status="running",
                started_at=completed,
                completed_at=None,
            ),
        ],
    )


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@router.get(
    "/{agent_id}/delegations",
    response_model=DelegationGraphResponse,
    responses={404: {"description": "Agent not found"}},
    summary="Fetch the delegation graph rooted at an agent",
)
async def get_delegations(
    agent_id: str = Path(..., description="Root agent id", pattern=r"^[a-zA-Z0-9_-]+$"),
) -> DelegationGraphResponse:
    """Today: returns a fixed 3-node / 2-edge demo graph for any agent_id.

    Phase 5: reads from a live ``MultiAgentOrchestrator.snapshot()`` so
    B's reactflow component shows the actual runtime topology.
    """
    if not agent_id:
        # FastAPI's path validator catches empty paths before this point;
        # the explicit check is here so reviewers don't have to puzzle
        # over what guarantees ``agent_id`` is non-empty.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="agent_id required",
        )
    return _mock_graph(agent_id)
