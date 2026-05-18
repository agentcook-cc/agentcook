"""Compile declarative YAML router config into LangGraph StateGraph.

This is agentcook's key differentiator:
- LangGraph: imperative (write Python to define state machines)
- agentcook: declarative (YAML/JSON config, compiled to LangGraph at runtime)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

import yaml

class AgentState(TypedDict):
    """State shared across all agents in the graph."""
    messages: list[dict[str, str]]
    current_agent: str
    task: str

@dataclass
class AgentConfig:
    """Parsed agent configuration."""
    name: str
    description: str
    trigger_patterns: list[str]
    model: str
    system_prompt: str
    is_fallback: bool = False

def load_config(config_path: str) -> tuple[list[AgentConfig], str]:
    """Load and parse router YAML config."""
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    agents = []
    for agent_data in raw["agents"]:
        agents.append(AgentConfig(
            name=agent_data["name"],
            description=agent_data["description"],
            trigger_patterns=agent_data.get("trigger_patterns", []),
            model=agent_data.get("model", "gpt-4o-mini"),
            system_prompt=agent_data.get("system_prompt", ""),
            is_fallback=agent_data.get("is_fallback", False),
        ))

    routing_strategy = raw.get("routing_strategy", "pattern_match")
    return agents, routing_strategy

def _make_router_node(agents: list[AgentConfig]):
    """Create router node that dispatches to the right agent."""
    def router(state: AgentState) -> AgentState:
        task = state["task"].lower()
        for agent in agents:
            if agent.is_fallback:
                continue
            for pattern in agent.trigger_patterns:
                if re.search(pattern, task, re.IGNORECASE):
                    return {**state, "current_agent": agent.name}
        # Fallback
        fallback = next((a for a in agents if a.is_fallback), agents[-1])
        return {**state, "current_agent": fallback.name}
    return router

def _make_agent_node(agent_config: AgentConfig):
    """Create an agent node (POC: echo mode, no real LLM call)."""
    def agent_node(state: AgentState) -> AgentState:
        response = {
            "role": "assistant",
            "content": f"[{agent_config.name}] (model={agent_config.model}) "
                       f"处理任务: {state['task']}"
        }
        return {
            **state,
            "messages": state["messages"] + [response]
        }
    return agent_node

def compile_router_config(config_path: str):
    """Compile YAML config into a LangGraph StateGraph.
    
    This is the core of agentcook's declarative multi-agent system.
    """
    from langgraph.graph import StateGraph, START, END

    agents, routing_strategy = load_config(config_path)

    graph = StateGraph(AgentState)

    # Add router node
    graph.add_node("router", _make_router_node(agents))

    # Add agent nodes
    for agent in agents:
        graph.add_node(agent.name, _make_agent_node(agent))

    # Edges: START → router
    graph.add_edge(START, "router")

    # Conditional edges: router → specific agent
    def route_to_agent(state: AgentState) -> str:
        return state["current_agent"]

    agent_names = {agent.name: agent.name for agent in agents}
    graph.add_conditional_edges("router", route_to_agent, agent_names)

    # Each agent → END
    for agent in agents:
        graph.add_edge(agent.name, END)

    return graph.compile()
