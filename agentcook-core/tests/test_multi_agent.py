"""Tests for agentcook_core.multi_agent."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from agentcook_core.multi_agent import (
    AgentNode,
    AgentNodeConfig,
    MultiAgentOrchestrator,
    RouterConfig,
    RoutingStrategy,
    parse_router_config,
    pattern_match_route,
)
from agentcook_core.types import Message

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class MockNode:
    """Mock AgentNode for testing."""

    def __init__(self, name: str, response_content: str = ""):
        self._name = name
        self._response = response_content or f"Response from {name}"
        self.call_count = 0
        self.last_messages: Sequence[Message] = ()

    @property
    def name(self) -> str:
        return self._name

    async def execute(
        self, messages: Sequence[Message], *, context: dict[str, Any] | None = None
    ) -> Message:
        self.call_count += 1
        self.last_messages = messages
        return Message(role="assistant", content=self._response)


RESEARCH_CFG = AgentNodeConfig(
    name="research",
    description="Research agent",
    model="gpt-4o-mini",
    trigger_patterns=("搜索", "查找", "research", "search"),
)

CODE_CFG = AgentNodeConfig(
    name="code",
    description="Code agent",
    model="gpt-4o",
    trigger_patterns=("代码", "编程", "code", "debug", "实现"),
)

GENERAL_CFG = AgentNodeConfig(
    name="general",
    description="General fallback",
    model="gpt-4o-mini",
    is_fallback=True,
)


@pytest.fixture
def router_config() -> RouterConfig:
    return RouterConfig(
        name="test-router",
        description="Test multi-agent router",
        agents=(RESEARCH_CFG, CODE_CFG, GENERAL_CFG),
        strategy=RoutingStrategy.PATTERN_MATCH,
    )


@pytest.fixture
def nodes() -> dict[str, MockNode]:
    return {
        "research": MockNode("research"),
        "code": MockNode("code"),
        "general": MockNode("general"),
    }


# ---------------------------------------------------------------------------
# pattern_match_route
# ---------------------------------------------------------------------------

class TestPatternMatchRoute:
    @pytest.mark.unit
    def test_routes_to_research(self):
        agents = (RESEARCH_CFG, CODE_CFG, GENERAL_CFG)
        assert pattern_match_route("帮我搜索一下天气", agents) == "research"

    @pytest.mark.unit
    def test_routes_to_code(self):
        agents = (RESEARCH_CFG, CODE_CFG, GENERAL_CFG)
        assert pattern_match_route("帮我写一段代码", agents) == "code"

    @pytest.mark.unit
    def test_routes_to_code_english(self):
        agents = (RESEARCH_CFG, CODE_CFG, GENERAL_CFG)
        assert pattern_match_route("please debug this function", agents) == "code"

    @pytest.mark.unit
    def test_fallback_when_no_match(self):
        agents = (RESEARCH_CFG, CODE_CFG, GENERAL_CFG)
        assert pattern_match_route("今天心情不错", agents) == "general"

    @pytest.mark.unit
    def test_fallback_to_last_if_no_fallback_flag(self):
        agents = (
            AgentNodeConfig(name="a", description="", trigger_patterns=("xyz",)),
            AgentNodeConfig(name="b", description=""),
        )
        assert pattern_match_route("hello", agents) == "b"

    @pytest.mark.unit
    def test_case_insensitive(self):
        agents = (RESEARCH_CFG, CODE_CFG, GENERAL_CFG)
        assert pattern_match_route("SEARCH for info", agents) == "research"


# ---------------------------------------------------------------------------
# parse_router_config
# ---------------------------------------------------------------------------

class TestParseRouterConfig:
    @pytest.mark.unit
    def test_full_config(self):
        raw = {
            "router": {"name": "my-router", "description": "desc"},
            "agents": [
                {
                    "name": "a1",
                    "description": "first",
                    "model": "gpt-4o",
                    "trigger_patterns": ["hello"],
                    "is_fallback": False,
                },
                {
                    "name": "a2",
                    "description": "fallback",
                    "is_fallback": True,
                },
            ],
            "routing_strategy": "pattern_match",
        }
        config = parse_router_config(raw)
        assert config.name == "my-router"
        assert len(config.agents) == 2
        assert config.agents[0].name == "a1"
        assert config.agents[0].trigger_patterns == ("hello",)
        assert config.agents[1].is_fallback is True
        assert config.strategy == RoutingStrategy.PATTERN_MATCH

    @pytest.mark.unit
    def test_defaults(self):
        raw = {"agents": [{"name": "x", "description": "y"}]}
        config = parse_router_config(raw)
        assert config.name == "default-router"
        assert config.agents[0].model == "gpt-4o"
        assert config.strategy == RoutingStrategy.PATTERN_MATCH

    @pytest.mark.unit
    def test_unknown_strategy_falls_back(self):
        raw = {"agents": [{"name": "x"}], "routing_strategy": "unknown_stuff"}
        config = parse_router_config(raw)
        assert config.strategy == RoutingStrategy.PATTERN_MATCH

    @pytest.mark.unit
    def test_with_rules(self):
        raw = {
            "agents": [{"name": "x"}],
            "rules": [
                {"target": "x", "patterns": ["hi"], "priority": 10}
            ],
        }
        config = parse_router_config(raw)
        assert len(config.rules) == 1
        assert config.rules[0].target == "x"
        assert config.rules[0].priority == 10


# ---------------------------------------------------------------------------
# MultiAgentOrchestrator (simple mode)
# ---------------------------------------------------------------------------

class TestOrchestratorSimpleMode:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_routes_to_research(self, router_config, nodes):
        orch = MultiAgentOrchestrator(router_config, nodes)
        messages = [Message(role="user", content="帮我搜索Python教程")]
        result = await orch.run(messages, task="帮我搜索Python教程")
        assert result.output.role == "assistant"
        assert "research" in result.route_path
        assert nodes["research"].call_count == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_routes_to_code(self, router_config, nodes):
        orch = MultiAgentOrchestrator(router_config, nodes)
        messages = [Message(role="user", content="帮我实现排序算法")]
        result = await orch.run(messages, task="帮我实现排序算法")
        assert "code" in result.route_path
        assert nodes["code"].call_count == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fallback(self, router_config, nodes):
        orch = MultiAgentOrchestrator(router_config, nodes)
        messages = [Message(role="user", content="聊聊天吧")]
        result = await orch.run(messages, task="聊聊天吧")
        assert "general" in result.route_path
        assert nodes["general"].call_count == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_uses_last_message_if_no_task(self, router_config, nodes):
        orch = MultiAgentOrchestrator(router_config, nodes)
        messages = [Message(role="user", content="search for cats")]
        result = await orch.run(messages)
        assert "research" in result.route_path

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_missing_node_raises(self, router_config):
        orch = MultiAgentOrchestrator(router_config, {"research": MockNode("research")})
        messages = [Message(role="user", content="随便聊")]
        with pytest.raises(RuntimeError, match="no node registered"):
            await orch.run(messages, task="随便聊")

    @pytest.mark.unit
    def test_node_names(self, router_config, nodes):
        orch = MultiAgentOrchestrator(router_config, nodes)
        assert set(orch.node_names) == {"research", "code", "general"}

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_result_metadata(self, router_config, nodes):
        orch = MultiAgentOrchestrator(router_config, nodes)
        messages = [Message(role="user", content="search")]
        result = await orch.run(messages, task="search")
        assert result.metadata["strategy"] == "pattern_match"


# ---------------------------------------------------------------------------
# MultiAgentOrchestrator (compiled mode)
# ---------------------------------------------------------------------------

class TestOrchestratorCompiledMode:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_compiled_graph_invoke(self, router_config, nodes):
        class FakeCompiled:
            async def ainvoke(self, state):
                return {
                    "messages": [{"role": "assistant", "content": "compiled result"}],
                    "current_agent": "code",
                }

        class FakeCompiler:
            def compile(self, config, nodes_dict):
                return FakeCompiled()

        orch = MultiAgentOrchestrator(router_config, nodes, compiler=FakeCompiler())
        messages = [Message(role="user", content="test")]
        result = await orch.run(messages, task="test")
        assert result.output.content == "compiled result"
        assert result.metadata.get("compiled") is True
        assert "code" in result.route_path

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_compiled_sync_invoke(self, router_config, nodes):
        class FakeSyncCompiled:
            def invoke(self, state):
                return {
                    "messages": [{"role": "assistant", "content": "sync result"}],
                    "current_agent": "research",
                }

        class FakeSyncCompiler:
            def compile(self, config, nodes_dict):
                return FakeSyncCompiled()

        orch = MultiAgentOrchestrator(router_config, nodes, compiler=FakeSyncCompiler())
        messages = [Message(role="user", content="test")]
        result = await orch.run(messages, task="test")
        assert result.output.content == "sync result"


# ---------------------------------------------------------------------------
# AgentNode protocol check
# ---------------------------------------------------------------------------

class TestAgentNodeProtocol:
    @pytest.mark.unit
    def test_mock_node_satisfies_protocol(self):
        node = MockNode("test")
        assert isinstance(node, AgentNode)
