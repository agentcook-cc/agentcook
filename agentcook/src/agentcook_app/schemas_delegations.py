"""Pydantic schemas for the Delegations API (Day 29 scaffolding).

The Delegations endpoint surfaces the runtime graph of one Agent
delegating sub-tasks to another — the data backing B's Day 31
multi-agent reactflow visualization. Today's mock returns a simple
node-and-edge view; Phase 5 wires it through ``MultiAgentOrchestrator``
to read live router state.

Kept in a separate module from ``schemas.py`` so the Day 31 spec bump
shows a clean diff (same hygiene rule we used for ``schemas_skills.py``
on the Day 27→28 path).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DelegationStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]


class DelegationNode(BaseModel):
    """One agent in the delegation graph (a reactflow node)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Stable agent identifier within this graph.")
    name: str = Field(..., description="Display label.")
    role: str = Field(..., description="Agent role (planner / coder / reviewer / ...).")


class DelegationEdge(BaseModel):
    """A single delegation event from ``from_id`` to ``to_id`` (a reactflow edge)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Stable edge identifier.")
    from_id: str = Field(..., description="Delegator agent id.")
    to_id: str = Field(..., description="Delegate agent id.")
    task: str = Field(..., description="Short description of the delegated task.")
    status: DelegationStatus = Field(..., description="Lifecycle state of the delegation.")
    started_at: str = Field(..., description="ISO-8601 UTC timestamp.")
    completed_at: str | None = Field(default=None, description="ISO-8601 UTC; null while in-flight.")


class DelegationGraphResponse(BaseModel):
    """``GET /api/v1/agents/{agent_id}/delegations`` envelope."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(..., description="Root agent the graph is centred on.")
    nodes: list[DelegationNode] = Field(..., description="All agents that participated.")
    edges: list[DelegationEdge] = Field(..., description="Delegation events, oldest first.")


__all__ = [
    "DelegationEdge",
    "DelegationGraphResponse",
    "DelegationNode",
    "DelegationStatus",
]
