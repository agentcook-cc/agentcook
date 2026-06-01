"""Declarative multi-agent orchestration layer (ADR-002).

agentcook's differentiator vs raw LangGraph:
- **LangGraph** is imperative — you write Python to define state machines.
- **agentcook** is declarative — a :class:`RouterConfig` (JSON/YAML) is
  compiled into a LangGraph ``StateGraph`` at runtime.

This module lives in ``agentcook-core`` (stdlib-only) and defines:

1. :class:`AgentNode` — execution contract for each sub-agent.
2. :class:`RouterConfig` / :class:`RouteRule` — declarative routing
   specification (pattern-match / LLM-classify / tool-based).
3. :class:`MultiAgentOrchestrator` — runtime executor that dispatches
   messages through the compiled graph.
4. :func:`compile_graph` — the core compilation function (returns an
   opaque ``CompiledGraph`` handle the orchestrator consumes).

The actual LangGraph dependency is NOT in this file.  A
``GraphCompiler`` protocol is defined so downstream packages inject the
real ``langgraph`` compiler.  Tests in agentcook-core can validate
routing logic without any LangGraph import.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from agentcook_core.tracing import get_tracer
from agentcook_core.types import Message

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Routing strategy
# ---------------------------------------------------------------------------

class RoutingStrategy(str, Enum):
    """How the router selects the next agent."""

    PATTERN_MATCH = "pattern_match"
    LLM_CLASSIFY = "llm_classify"
    TOOL_ROUTE = "tool_route"


# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class RouteRule:
    """A single routing rule: if *patterns* match → route to *target*."""

    target: str
    patterns: tuple[str, ...] = ()
    description: str = ""
    priority: int = 0


@dataclass(frozen=True, slots=True)
class AgentNodeConfig:
    """Declarative configuration for one sub-agent in the graph."""

    name: str
    description: str
    model: str = "gpt-4o"
    system_prompt: str = ""
    is_fallback: bool = False
    trigger_patterns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RouterConfig:
    """Complete declarative multi-agent routing specification.

    Serialisable to/from JSON or YAML.  The :func:`compile_graph`
    function consumes this to produce an executable graph.
    """

    name: str
    description: str = ""
    agents: tuple[AgentNodeConfig, ...] = ()
    rules: tuple[RouteRule, ...] = ()
    strategy: RoutingStrategy = RoutingStrategy.PATTERN_MATCH
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# AgentNode protocol (execution contract)
# ---------------------------------------------------------------------------

@runtime_checkable
class AgentNode(Protocol):
    """Execution contract for a sub-agent node in the graph.

    Each node receives the conversation state and returns an updated
    state. The orchestrator is responsible for passing state between
    nodes according to the compiled graph topology.
    """

    @property
    def name(self) -> str: ...

    async def execute(
        self,
        messages: Sequence[Message],
        *,
        context: dict[str, Any] | None = None,
    ) -> Message:
        """Run one turn and return the assistant response message."""
        ...


# ---------------------------------------------------------------------------
# GraphCompiler protocol (injected — LangGraph lives downstream)
# ---------------------------------------------------------------------------

@runtime_checkable
class GraphCompiler(Protocol):
    """Compiles a :class:`RouterConfig` into an executable graph handle.

    The returned ``compiled`` object is opaque to core — the
    :class:`MultiAgentOrchestrator` calls its ``invoke`` / ``stream``
    methods through the :class:`CompiledGraph` protocol.
    """

    def compile(self, config: RouterConfig, nodes: dict[str, AgentNode]) -> Any:
        """Return a compiled graph object (e.g. LangGraph CompiledStateGraph)."""
        ...


# ---------------------------------------------------------------------------
# Built-in pattern-match router (no LangGraph needed)
# ---------------------------------------------------------------------------

def pattern_match_route(
    task: str,
    agents: Sequence[AgentNodeConfig],
) -> str:
    """Route *task* to the best agent using regex pattern matching.

    Returns the agent name. Falls back to the agent marked
    ``is_fallback=True``, or the last agent if none is marked.
    """
    task_lower = task.lower()
    for agent in agents:
        if agent.is_fallback:
            continue
        for pattern in agent.trigger_patterns:
            if re.search(pattern, task_lower, re.IGNORECASE):
                return agent.name

    fallback = next((a for a in agents if a.is_fallback), None)
    return fallback.name if fallback else agents[-1].name


# ---------------------------------------------------------------------------
# Orchestrator result
# ---------------------------------------------------------------------------

@dataclass
class OrchestrationResult:
    """Result of a multi-agent orchestration run."""

    output: Message
    route_path: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# MultiAgentOrchestrator
# ---------------------------------------------------------------------------

class MultiAgentOrchestrator:
    """Runtime executor for multi-agent graphs.

    Can operate in two modes:
    1. **Compiled mode** (with a ``GraphCompiler``): full LangGraph
       state-machine execution with conditional edges, loops, etc.
    2. **Simple mode** (no compiler): uses built-in
       :func:`pattern_match_route` for single-hop dispatch.

    Simple mode is sufficient for unit tests and basic deployments;
    compiled mode unlocks LangGraph's full power (cycles, human-in-loop,
    tool routing, parallel branches).
    """

    def __init__(
        self,
        config: RouterConfig,
        nodes: dict[str, AgentNode],
        *,
        compiler: GraphCompiler | None = None,
    ) -> None:
        self._config = config
        self._nodes = nodes
        self._compiler = compiler
        self._compiled_graph: Any | None = None

        if compiler is not None:
            self._compiled_graph = compiler.compile(config, nodes)

    @property
    def config(self) -> RouterConfig:
        return self._config

    @property
    def node_names(self) -> list[str]:
        return list(self._nodes.keys())

    async def run(
        self,
        messages: Sequence[Message],
        *,
        task: str = "",
        context: dict[str, Any] | None = None,
    ) -> OrchestrationResult:
        """Execute the orchestration graph.

        In compiled mode, delegates to the compiled graph's invoke.
        In simple mode, does pattern-match → single node execution.
        """
        with get_tracer().start_span(
            "multi_agent.run",
            attributes={
                "agentcook.router.strategy": self._config.strategy.value,
                "agentcook.router.node_count": len(self._nodes),
                "agentcook.router.compiled": self._compiled_graph is not None,
                "agentcook.messages.count": len(messages),
            },
        ):
            if self._compiled_graph is not None:
                return await self._run_compiled(messages, task=task, context=context)
            return await self._run_simple(messages, task=task, context=context)

    async def _run_simple(
        self,
        messages: Sequence[Message],
        *,
        task: str,
        context: dict[str, Any] | None,
    ) -> OrchestrationResult:
        """Simple single-hop dispatch via pattern matching."""
        route_target = task or (messages[-1].content if messages else "")
        agent_name = pattern_match_route(route_target, self._config.agents)

        node = self._nodes.get(agent_name)
        if node is None:
            raise RuntimeError(
                f"Routed to {agent_name!r} but no node registered. "
                f"Available: {list(self._nodes.keys())}"
            )

        logger.info("Routing to %r (strategy=%s)", agent_name, self._config.strategy.value)
        output = await node.execute(messages, context=context)

        return OrchestrationResult(
            output=output,
            route_path=["router", agent_name],
            metadata={"strategy": self._config.strategy.value},
        )

    async def _run_compiled(
        self,
        messages: Sequence[Message],
        *,
        task: str,
        context: dict[str, Any] | None,
    ) -> OrchestrationResult:
        """Delegate to the compiled graph (LangGraph or equivalent)."""
        if self._compiled_graph is None:
            raise RuntimeError("No compiled graph available")

        # The compiled graph's invoke/ainvoke signature varies by engine.
        # We support both sync and async patterns via duck typing.
        state = {
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "task": task,
            "current_agent": "",
        }

        if hasattr(self._compiled_graph, "ainvoke"):
            result_state = await self._compiled_graph.ainvoke(state)
        elif hasattr(self._compiled_graph, "invoke"):
            result_state = self._compiled_graph.invoke(state)
        else:
            raise RuntimeError("Compiled graph has no invoke/ainvoke method")

        result_messages = result_state.get("messages", [])
        last_msg = result_messages[-1] if result_messages else {}
        output = Message(
            role=last_msg.get("role", "assistant"),
            content=last_msg.get("content", ""),
        )

        return OrchestrationResult(
            output=output,
            route_path=["router", result_state.get("current_agent", "unknown")],
            metadata={"strategy": self._config.strategy.value, "compiled": True},
        )


# ---------------------------------------------------------------------------
# Config parsing helpers
# ---------------------------------------------------------------------------

def parse_router_config(raw: dict[str, Any]) -> RouterConfig:
    """Parse a raw dict (from JSON/YAML) into a :class:`RouterConfig`."""
    router_section = raw.get("router", {})
    agents_raw = raw.get("agents", [])
    rules_raw = raw.get("rules", [])
    strategy_str = raw.get("routing_strategy", "pattern_match")

    agents = tuple(
        AgentNodeConfig(
            name=a["name"],
            description=a.get("description", ""),
            model=a.get("model", "gpt-4o"),
            system_prompt=a.get("system_prompt", ""),
            is_fallback=a.get("is_fallback", False),
            trigger_patterns=tuple(a.get("trigger_patterns", [])),
        )
        for a in agents_raw
    )

    rules = tuple(
        RouteRule(
            target=r["target"],
            patterns=tuple(r.get("patterns", [])),
            description=r.get("description", ""),
            priority=r.get("priority", 0),
        )
        for r in rules_raw
    )

    try:
        strategy = RoutingStrategy(strategy_str)
    except ValueError:
        strategy = RoutingStrategy.PATTERN_MATCH

    return RouterConfig(
        name=router_section.get("name", "default-router"),
        description=router_section.get("description", ""),
        agents=agents,
        rules=rules,
        strategy=strategy,
    )


__all__ = [
    "AgentNode",
    "AgentNodeConfig",
    "GraphCompiler",
    "MultiAgentOrchestrator",
    "OrchestrationResult",
    "RouteRule",
    "RouterConfig",
    "RoutingStrategy",
    "parse_router_config",
    "pattern_match_route",
]
