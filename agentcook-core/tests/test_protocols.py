"""Contract tests for the 5 core protocols.

Each test builds a minimal stub satisfying the protocol's structural
contract and asserts:

1. A correctly-shaped stub passes ``isinstance`` against the
   :func:`runtime_checkable` protocol.
2. A stub missing any required attribute fails ``isinstance``.
3. Where the protocol declares ``async`` methods, the stub's coroutine
   returns the expected value type.

These tests do not verify *behavior* — they verify only that the
contract surface is what downstream packages will see.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

pytestmark = pytest.mark.unit

from agentcook_core import (  # noqa: E402
    AgentProtocol,
    AgentResponse,
    ChatChunk,
    ChatResponse,
    ConnectorConfig,
    ConnectorKind,
    ConnectorProtocol,
    IdentityCard,
    IdentityProtocol,
    LLMProviderProtocol,
    MemoryEvent,
    MemoryHit,
    MemoryRecall,
    MemoryStoreProtocol,
    Message,
    ModelSpec,
    PluginManifest,
    PluginProtocol,
    SkillManifest,
    SkillProtocol,
    SoulConfig,
    SoulProtocol,
    TokenUsage,
    ToolCall,
    ToolProtocol,
    ToolResult,
)

# --------------------------- Tool ---------------------------

class _StubTool:
    name = "echo"
    description = "Return the input verbatim."
    parameters_schema = {"type": "object", "properties": {"text": {"type": "string"}}}

    async def invoke(self, arguments: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, output=arguments.get("text", ""))


async def test_tool_protocol_contract() -> None:
    tool = _StubTool()
    assert isinstance(tool, ToolProtocol)
    result = await tool.invoke({"text": "hi"})
    assert isinstance(result, ToolResult)
    assert result.success is True and result.output == "hi"


def test_tool_protocol_rejects_incomplete_stub() -> None:
    class Broken:
        name = "x"
        # missing description, parameters_schema, invoke
    assert not isinstance(Broken(), ToolProtocol)


# --------------------------- Skill ---------------------------

class _StubSkill:
    def __init__(self) -> None:
        self._manifest = SkillManifest(name="hello", description="say hi", version="1.0.0")

    @property
    def manifest(self) -> SkillManifest:
        return self._manifest

    def load(self) -> str:
        return "# Hello\n\nSay hi to the user."


def test_skill_protocol_contract() -> None:
    skill = _StubSkill()
    assert isinstance(skill, SkillProtocol)
    assert skill.manifest.name == "hello"
    assert skill.load().startswith("# Hello")


# --------------------------- Connector ---------------------------

class _StubConnector:
    def __init__(self) -> None:
        self._config = ConnectorConfig(
            name="github",
            kind=ConnectorKind.MCP,
            config={"command": "npx", "args": ["@modelcontextprotocol/server-github"]},
        )

    @property
    def config(self) -> ConnectorConfig:
        return self._config

    async def open(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def tools(self) -> Sequence[ToolProtocol]:
        return ()


async def test_connector_protocol_contract() -> None:
    conn = _StubConnector()
    assert isinstance(conn, ConnectorProtocol)
    assert conn.config.kind is ConnectorKind.MCP
    await conn.open()
    assert await conn.tools() == ()
    await conn.close()


def test_connector_kind_covers_im_webhook() -> None:
    """ConnectorKind must include WEBHOOK for IM event-callback connectors."""
    assert ConnectorKind.WEBHOOK.value == "webhook"
    cfg = ConnectorConfig(
        name="dingtalk-events",
        kind=ConnectorKind.WEBHOOK,
        config={"url": "https://example.com/dingtalk/callback", "secret": "***"},
    )
    assert cfg.kind is ConnectorKind.WEBHOOK
    assert {k.value for k in ConnectorKind} == {"mcp", "oauth", "http", "custom", "webhook"}


# --------------------------- Agent ---------------------------

class _StubAgent:
    name = "echo-agent"
    description = "Echoes the last user message."
    model = ModelSpec(provider="openai", name="gpt-4o-mini")

    async def run(
        self,
        messages: Sequence[Message],
        *,
        context: dict[str, Any] | None = None,
    ) -> AgentResponse:
        last = messages[-1].content if messages else ""
        return AgentResponse(output=last)


async def test_agent_protocol_contract() -> None:
    agent = _StubAgent()
    assert isinstance(agent, AgentProtocol)
    resp = await agent.run([Message(role="user", content="ping")])
    assert isinstance(resp, AgentResponse)
    assert resp.output == "ping"


# --------------------------- Plugin ---------------------------

class _StubPlugin:
    def __init__(self) -> None:
        self._manifest = PluginManifest(
            name="hello-world",
            display_name="Hello World",
            version="1.0.0",
            description="Minimal plugin demonstrating the protocol shape.",
        )
        self._agents: tuple[AgentProtocol, ...] = (_StubAgent(),)
        self._skills: tuple[SkillProtocol, ...] = (_StubSkill(),)
        self._connectors: tuple[ConnectorProtocol, ...] = ()

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    @property
    def agents(self) -> Sequence[AgentProtocol]:
        return self._agents

    @property
    def skills(self) -> Sequence[SkillProtocol]:
        return self._skills

    @property
    def connectors(self) -> Sequence[ConnectorProtocol]:
        return self._connectors

    async def activate(self) -> None:
        return None

    async def deactivate(self) -> None:
        return None


async def test_plugin_protocol_contract() -> None:
    plugin = _StubPlugin()
    assert isinstance(plugin, PluginProtocol)
    assert plugin.manifest.name == "hello-world"
    assert isinstance(plugin.agents[0], AgentProtocol)
    assert isinstance(plugin.skills[0], SkillProtocol)
    await plugin.activate()
    await plugin.deactivate()


# --------------------------- value types ---------------------------

def test_dataclass_value_types_are_frozen() -> None:
    msg = Message(role="user", content="hi")
    with pytest.raises(Exception):
        msg.content = "x"  # type: ignore[misc]


def test_token_usage_total() -> None:
    usage = AgentResponse(output="").usage
    assert usage.total == 0
    assert TokenUsage(input=10, output=20).total == 30


# --------------------------- Message tool-use fields ---------------------------

def test_message_supports_tool_call_round_trip() -> None:
    """An assistant turn requesting a tool, followed by a tool reply."""
    call = ToolCall(id="call_1", name="search", arguments={"q": "agentcook"})
    assistant = Message(role="assistant", content="", tool_calls=(call,))
    assert assistant.tool_calls is not None and assistant.tool_calls[0].name == "search"

    tool_reply = Message(
        role="tool",
        content='{"hits": 3}',
        name="search",
        tool_call_id="call_1",
    )
    assert tool_reply.tool_call_id == "call_1"
    assert tool_reply.name == "search"


def test_message_defaults_remain_backward_compatible() -> None:
    """Existing 2-field call sites still construct cleanly."""
    msg = Message(role="user", content="hi")
    assert msg.tool_calls is None and msg.tool_call_id is None and msg.name is None


# --------------------------- LLMProvider ---------------------------

class _StubLLMProvider:
    model_name = "stub-llm-1"
    context_window = 8000

    async def chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolProtocol] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        text = messages[-1].content if messages else ""
        reply = Message(role="assistant", content=f"echo: {text}")
        return ChatResponse(message=reply, usage=TokenUsage(input=10, output=5), finish_reason="stop")

    async def stream_chat(  # async-generator factory
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolProtocol] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        for piece in ("hel", "lo"):
            yield ChatChunk(delta_content=piece)
        yield ChatChunk(delta_content="", finish_reason="stop")

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)


async def test_llm_provider_protocol_contract() -> None:
    p = _StubLLMProvider()
    assert isinstance(p, LLMProviderProtocol)
    resp = await p.chat([Message(role="user", content="ping")])
    assert isinstance(resp, ChatResponse)
    assert resp.message.role == "assistant" and resp.message.content == "echo: ping"
    assert resp.usage.total == 15 and resp.finish_reason == "stop"


async def test_llm_provider_streams_chunks() -> None:
    p = _StubLLMProvider()
    chunks = [c async for c in p.stream_chat([Message(role="user", content="hi")])]
    assert [c.delta_content for c in chunks] == ["hel", "lo", ""]
    assert chunks[-1].finish_reason == "stop"


# --------------------------- Identity / Soul / Memory (ADR-011) ---------------------------

class _StubIdentity:
    def __init__(self) -> None:
        self._card = IdentityCard(
            name="hello-agent",
            role="assistant",
            created_at="2026-05-18T00:00:00Z",
            scopes=frozenset({"chat", "search"}),
        )

    @property
    def card(self) -> IdentityCard:
        return self._card


def test_identity_protocol_contract() -> None:
    identity = _StubIdentity()
    assert isinstance(identity, IdentityProtocol)
    assert identity.card.name == "hello-agent"
    assert "chat" in identity.card.scopes


def test_identity_card_is_frozen() -> None:
    card = IdentityCard(name="x", role="r", created_at="2026-05-18T00:00:00Z")
    with pytest.raises(Exception):
        card.name = "y"  # type: ignore[misc]


class _StubSoul:
    def __init__(self) -> None:
        self._config = SoulConfig(tone="warm", language_style="friendly")

    @property
    def config(self) -> SoulConfig:
        return self._config

    async def replace(self, config: SoulConfig) -> SoulConfig:
        self._config = config
        return config


async def test_soul_protocol_contract_round_trip() -> None:
    soul = _StubSoul()
    assert isinstance(soul, SoulProtocol)
    assert soul.config.tone == "warm"
    new_cfg = SoulConfig(tone="precise", language_style="technical", values=("clarity",))
    persisted = await soul.replace(new_cfg)
    assert persisted == new_cfg and soul.config == new_cfg


class _InMemoryStore:
    """Tiny in-memory MemoryStore for protocol-shape verification."""

    def __init__(self) -> None:
        self._session: dict[tuple[str, str], Any] = {}
        self._events: dict[str, list[MemoryEvent]] = {}

    async def remember_session(
        self,
        session_id: str,
        key: str,
        value: Any,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        self._session[(session_id, key)] = value

    async def recall_session(self, session_id: str, key: str) -> Any | None:
        return self._session.get((session_id, key))

    async def append_event(self, agent_id: str, event: MemoryEvent) -> None:
        self._events.setdefault(agent_id, []).append(event)

    async def stream_events(
        self,
        agent_id: str,
        *,
        since: str | None = None,
        kind: str | None = None,
        limit: int = 100,
    ) -> Sequence[MemoryEvent]:
        events = self._events.get(agent_id, [])
        if kind:
            events = [e for e in events if e.kind == kind]
        return events[-limit:]

    async def search(
        self,
        agent_id: str,
        query: str,
        *,
        top_k: int = 5,
    ) -> MemoryRecall:
        hits = tuple(
            MemoryHit(content=e.content, score=1.0, event=e)
            for e in self._events.get(agent_id, [])
            if query.lower() in e.content.lower()
        )[:top_k]
        return MemoryRecall(query=query, hits=hits)


async def test_memory_store_protocol_session_kv_round_trip() -> None:
    store = _InMemoryStore()
    assert isinstance(store, MemoryStoreProtocol)
    await store.remember_session("sess-1", "last_query", "agentcook")
    assert await store.recall_session("sess-1", "last_query") == "agentcook"
    assert await store.recall_session("sess-1", "missing") is None


async def test_memory_store_protocol_event_stream_and_search() -> None:
    store = _InMemoryStore()
    await store.append_event(
        "agent-A",
        MemoryEvent(timestamp="2026-05-18T00:00:00Z", kind="observation", content="user likes pgvector"),
    )
    await store.append_event(
        "agent-A",
        MemoryEvent(timestamp="2026-05-18T00:01:00Z", kind="tool_use", content="ran web_search"),
    )
    events = await store.stream_events("agent-A", kind="observation")
    assert len(events) == 1 and "pgvector" in events[0].content

    recall = await store.search("agent-A", "pgvector")
    assert recall.query == "pgvector"
    assert len(recall.hits) == 1 and recall.hits[0].score == 1.0
