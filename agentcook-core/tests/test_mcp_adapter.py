"""Tests for agentcook_core.mcp_adapter."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from agentcook_core.mcp_adapter import (
    McpClient,
    McpServerConfig,
    McpToolAdapter,
    McpToolRegistry,
    McpToolSchema,
    McpTransportMode,
)
from agentcook_core.protocols import ToolProtocol

# ---------------------------------------------------------------------------
# Mock transport
# ---------------------------------------------------------------------------

class MockTransport:
    """Mock MCP transport for unit tests."""

    def __init__(
        self,
        tools: list[McpToolSchema] | None = None,
        call_response: dict[str, Any] | None = None,
        fail_on_call: bool = False,
    ):
        self._tools = tools or []
        self._call_response = call_response or {"content": "mock result"}
        self._connected = False
        self._fail_on_call = fail_on_call
        self.connect_calls = 0
        self.disconnect_calls = 0
        self.call_tool_calls: list[tuple[str, dict]] = []

    async def connect(self, config: McpServerConfig) -> None:
        self.connect_calls += 1
        self._connected = True

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        self._connected = False

    async def list_tools(self) -> Sequence[McpToolSchema]:
        return self._tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.call_tool_calls.append((tool_name, arguments))
        if self._fail_on_call:
            raise RuntimeError(f"MCP call failed: {tool_name}")
        return self._call_response

    @property
    def is_connected(self) -> bool:
        return self._connected


SAMPLE_TOOLS = [
    McpToolSchema(
        name="web_search",
        description="Search the web",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
    ),
    McpToolSchema(
        name="read_file",
        description="Read a file from disk",
        input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
    ),
]


# ---------------------------------------------------------------------------
# McpToolAdapter
# ---------------------------------------------------------------------------

class TestMcpToolAdapter:
    @pytest.mark.unit
    def test_satisfies_tool_protocol(self):
        transport = MockTransport()
        adapter = McpToolAdapter(SAMPLE_TOOLS[0], transport, server_name="test")
        assert isinstance(adapter, ToolProtocol)

    @pytest.mark.unit
    def test_properties(self):
        transport = MockTransport()
        adapter = McpToolAdapter(SAMPLE_TOOLS[0], transport, server_name="s1")
        assert adapter.name == "web_search"
        assert adapter.description == "Search the web"
        assert "query" in adapter.parameters_schema.get("properties", {})

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invoke_success(self):
        transport = MockTransport(call_response={"content": "found 5 results"})
        adapter = McpToolAdapter(SAMPLE_TOOLS[0], transport, server_name="s1")
        result = await adapter.invoke({"query": "python"})
        assert result.success is True
        assert result.output == "found 5 results"
        assert result.metadata["server"] == "s1"
        assert result.metadata["tool"] == "web_search"
        assert transport.call_tool_calls == [("web_search", {"query": "python"})]

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invoke_failure(self):
        transport = MockTransport(fail_on_call=True)
        adapter = McpToolAdapter(SAMPLE_TOOLS[0], transport, server_name="s1")
        result = await adapter.invoke({"query": "test"})
        assert result.success is False
        assert "MCP call failed" in result.error


# ---------------------------------------------------------------------------
# McpClient
# ---------------------------------------------------------------------------

class TestMcpClient:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_connect_discovers_tools(self):
        transport = MockTransport(tools=SAMPLE_TOOLS)
        config = McpServerConfig(name="test-server", transport=McpTransportMode.STDIO)
        client = McpClient(config, transport)

        assert not client.is_connected
        await client.connect()
        assert client.is_connected
        assert len(client.tools) == 2
        assert client.tools[0].name == "web_search"
        assert client.tools[1].name == "read_file"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_call_tool_by_name(self):
        transport = MockTransport(tools=SAMPLE_TOOLS, call_response={"content": "ok"})
        config = McpServerConfig(name="s", transport=McpTransportMode.SSE, url="http://localhost:3000")
        client = McpClient(config, transport)
        await client.connect()

        result = await client.call_tool("web_search", {"query": "hi"})
        assert result.success is True
        assert result.output == "ok"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_call_tool_not_found(self):
        transport = MockTransport(tools=SAMPLE_TOOLS)
        config = McpServerConfig(name="s")
        client = McpClient(config, transport)
        await client.connect()

        result = await client.call_tool("nonexistent", {})
        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_disconnect_clears_tools(self):
        transport = MockTransport(tools=SAMPLE_TOOLS)
        config = McpServerConfig(name="s")
        client = McpClient(config, transport)
        await client.connect()
        assert len(client.tools) == 2

        await client.disconnect()
        assert len(client.tools) == 0
        assert not client.is_connected
        assert transport.disconnect_calls == 1


# ---------------------------------------------------------------------------
# McpToolRegistry
# ---------------------------------------------------------------------------

class TestMcpToolRegistry:
    @pytest.mark.unit
    def test_add_and_contains(self):
        transport = MockTransport(tools=SAMPLE_TOOLS)
        client = McpClient(McpServerConfig(name="a"), transport)
        registry = McpToolRegistry()
        registry.add(client)
        assert "a" in registry
        assert len(registry) == 1

    @pytest.mark.unit
    def test_add_duplicate_raises(self):
        transport = MockTransport()
        client = McpClient(McpServerConfig(name="a"), transport)
        registry = McpToolRegistry()
        registry.add(client)
        with pytest.raises(ValueError, match="already registered"):
            registry.add(client)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_connect_all(self):
        t1 = MockTransport(tools=[SAMPLE_TOOLS[0]])
        t2 = MockTransport(tools=[SAMPLE_TOOLS[1]])
        c1 = McpClient(McpServerConfig(name="s1"), t1)
        c2 = McpClient(McpServerConfig(name="s2"), t2)

        registry = McpToolRegistry()
        registry.add(c1)
        registry.add(c2)
        await registry.connect_all()

        assert t1.connect_calls == 1
        assert t2.connect_calls == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_all_tools_aggregates(self):
        t1 = MockTransport(tools=[SAMPLE_TOOLS[0]])
        t2 = MockTransport(tools=[SAMPLE_TOOLS[1]])
        c1 = McpClient(McpServerConfig(name="s1"), t1)
        c2 = McpClient(McpServerConfig(name="s2"), t2)

        registry = McpToolRegistry()
        registry.add(c1)
        registry.add(c2)
        await registry.connect_all()

        tools = registry.all_tools()
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"web_search", "read_file"}

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_disconnect_all(self):
        t1 = MockTransport(tools=SAMPLE_TOOLS)
        c1 = McpClient(McpServerConfig(name="s1"), t1)
        registry = McpToolRegistry()
        registry.add(c1)
        await registry.connect_all()
        await registry.disconnect_all()
        assert t1.disconnect_calls == 1

    @pytest.mark.unit
    def test_list_servers(self):
        registry = McpToolRegistry()
        registry.add(McpClient(McpServerConfig(name="x"), MockTransport()))
        registry.add(McpClient(McpServerConfig(name="y"), MockTransport()))
        assert set(registry.list_servers()) == {"x", "y"}

    @pytest.mark.unit
    def test_get_client(self):
        transport = MockTransport()
        client = McpClient(McpServerConfig(name="z"), transport)
        registry = McpToolRegistry()
        registry.add(client)
        assert registry.get_client("z") is client
        assert registry.get_client("nope") is None


# ---------------------------------------------------------------------------
# McpServerConfig
# ---------------------------------------------------------------------------

class TestMcpServerConfig:
    @pytest.mark.unit
    def test_stdio_config(self):
        cfg = McpServerConfig(
            name="local-mcp",
            transport=McpTransportMode.STDIO,
            command=("npx", "-y", "@modelcontextprotocol/server-filesystem"),
        )
        assert cfg.transport == McpTransportMode.STDIO
        assert cfg.command == ("npx", "-y", "@modelcontextprotocol/server-filesystem")

    @pytest.mark.unit
    def test_sse_config(self):
        cfg = McpServerConfig(
            name="remote-mcp",
            transport=McpTransportMode.SSE,
            url="http://localhost:3000/sse",
            headers={"Authorization": "Bearer tok"},
        )
        assert cfg.transport == McpTransportMode.SSE
        assert cfg.url == "http://localhost:3000/sse"

    @pytest.mark.unit
    def test_streamable_http_config(self):
        cfg = McpServerConfig(
            name="http-mcp",
            transport=McpTransportMode.STREAMABLE_HTTP,
            url="http://localhost:8080/mcp",
            timeout=60.0,
        )
        assert cfg.transport == McpTransportMode.STREAMABLE_HTTP
        assert cfg.timeout == 60.0
