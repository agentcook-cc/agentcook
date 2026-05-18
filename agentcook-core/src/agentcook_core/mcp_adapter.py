"""MCP (Model Context Protocol) adapter — client + Tool bridge.

Translates an external MCP Server's tool surface into agentcook's
internal :class:`ToolProtocol` instances so Agents can invoke them
transparently.

Design decisions:
- **stdlib-only** at the core layer: the actual transport (stdio
  subprocess / SSE / streamable-HTTP) is behind an injected
  :class:`McpTransport` protocol.  Concrete implementations live in
  the main shell (``agentcook``) or a dedicated ``agentcook-mcp`` pkg.
- **Three transport modes** per the MCP spec: stdio, sse,
  streamable-http.  Config declares which; the runtime picks the
  matching transport implementation.
- **Tool discovery is async**: ``McpClient.list_tools()`` fetches the
  server's tool manifest and wraps each into a :class:`McpToolAdapter`.
- **Integrates with multi_agent**: the tool list can be injected into
  any :class:`AgentNode`'s available tool set.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from agentcook_core.protocols import ToolProtocol
from agentcook_core.types import ToolResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Transport enum + config
# ---------------------------------------------------------------------------

class McpTransportMode(str, Enum):
    """MCP transport flavours per the spec."""

    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable-http"


@dataclass(frozen=True, slots=True)
class McpServerConfig:
    """Connection configuration for one MCP server.

    Attributes:
        name: Human-readable server identifier.
        transport: Which transport mode to use.
        command: For stdio — the command + args to spawn.
        url: For sse / streamable-http — the server endpoint.
        headers: Optional auth headers for HTTP-based transports.
        env: Optional env vars passed to stdio subprocess.
        timeout: Connection / call timeout in seconds.
    """

    name: str
    transport: McpTransportMode = McpTransportMode.STDIO
    command: tuple[str, ...] = ()
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0


# ---------------------------------------------------------------------------
# McpTransport protocol (injected)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class McpToolSchema:
    """Tool metadata returned by an MCP server's ``tools/list`` response."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class McpTransport(Protocol):
    """Async transport layer for MCP communication.

    Concrete implementations handle stdio pipe management, SSE
    connections, or HTTP streaming. This protocol fixes the shape
    so the adapter is transport-agnostic.
    """

    async def connect(self, config: McpServerConfig) -> None:
        """Establish the connection to the MCP server."""
        ...

    async def disconnect(self) -> None:
        """Gracefully close the connection."""
        ...

    async def list_tools(self) -> Sequence[McpToolSchema]:
        """Fetch the server's tool manifest (``tools/list``)."""
        ...

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Invoke a tool on the server (``tools/call``)."""
        ...

    @property
    def is_connected(self) -> bool:
        """Whether the transport is currently connected."""
        ...


# ---------------------------------------------------------------------------
# McpToolAdapter — bridges MCP tool → ToolProtocol
# ---------------------------------------------------------------------------

class McpToolAdapter:
    """Wraps a single MCP tool as an agentcook :class:`ToolProtocol`.

    Delegates ``invoke`` to the underlying :class:`McpTransport`.
    """

    def __init__(
        self,
        schema: McpToolSchema,
        transport: McpTransport,
        *,
        server_name: str = "",
    ) -> None:
        self._schema = schema
        self._transport = transport
        self._server_name = server_name

    @property
    def name(self) -> str:
        return self._schema.name

    @property
    def description(self) -> str:
        return self._schema.description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return self._schema.input_schema

    async def invoke(self, arguments: dict[str, Any]) -> ToolResult:
        """Call the MCP server tool and wrap the response."""
        try:
            raw = await self._transport.call_tool(self._schema.name, arguments)
            return ToolResult(
                success=True,
                output=raw.get("content", raw),
                metadata={"server": self._server_name, "tool": self._schema.name},
            )
        except Exception as exc:
            logger.warning(
                "MCP tool %s.%s failed: %s",
                self._server_name,
                self._schema.name,
                exc,
            )
            return ToolResult(
                success=False,
                error=str(exc),
                metadata={"server": self._server_name, "tool": self._schema.name},
            )


# Runtime check
assert isinstance(
    McpToolAdapter.__new__(McpToolAdapter), ToolProtocol
), "McpToolAdapter does not satisfy ToolProtocol"


# ---------------------------------------------------------------------------
# McpClient — lifecycle manager for one MCP server
# ---------------------------------------------------------------------------

class McpClient:
    """Client for a single MCP server.

    Manages connection lifecycle and exposes discovered tools as
    :class:`ToolProtocol` instances.
    """

    def __init__(self, config: McpServerConfig, transport: McpTransport) -> None:
        self._config = config
        self._transport = transport
        self._tools: list[McpToolAdapter] = []

    @property
    def config(self) -> McpServerConfig:
        return self._config

    @property
    def is_connected(self) -> bool:
        return self._transport.is_connected

    @property
    def tools(self) -> Sequence[McpToolAdapter]:
        return list(self._tools)

    async def connect(self) -> None:
        """Connect to the MCP server and discover tools."""
        await self._transport.connect(self._config)
        schemas = await self._transport.list_tools()
        self._tools = [
            McpToolAdapter(schema, self._transport, server_name=self._config.name)
            for schema in schemas
        ]
        logger.info(
            "McpClient(%s) connected — discovered %d tools",
            self._config.name,
            len(self._tools),
        )

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        """Call a tool by name (convenience wrapper)."""
        for tool in self._tools:
            if tool.name == tool_name:
                return await tool.invoke(arguments)
        return ToolResult(
            success=False,
            error=f"Tool {tool_name!r} not found on server {self._config.name!r}",
        )

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        await self._transport.disconnect()
        self._tools.clear()
        logger.info("McpClient(%s) disconnected", self._config.name)


# ---------------------------------------------------------------------------
# McpToolRegistry — aggregate multiple MCP servers
# ---------------------------------------------------------------------------

class McpToolRegistry:
    """Manages multiple MCP server connections and provides a unified
    tool pool.

    Usage::

        registry = McpToolRegistry()
        registry.add(client_a)
        registry.add(client_b)
        await registry.connect_all()
        tools = registry.all_tools()  # ToolProtocol instances from both servers
    """

    def __init__(self) -> None:
        self._clients: dict[str, McpClient] = {}

    def add(self, client: McpClient) -> None:
        """Register an MCP client (not yet connected)."""
        name = client.config.name
        if name in self._clients:
            raise ValueError(f"MCP server {name!r} already registered")
        self._clients[name] = client

    async def connect_all(self) -> None:
        """Connect all registered clients and discover their tools."""
        for name, client in self._clients.items():
            try:
                await client.connect()
            except Exception:
                logger.exception("Failed to connect MCP server %s", name)

    async def disconnect_all(self) -> None:
        """Disconnect all clients."""
        for client in self._clients.values():
            try:
                await client.disconnect()
            except Exception:
                logger.exception(
                    "Failed to disconnect MCP server %s", client.config.name
                )

    def all_tools(self) -> list[McpToolAdapter]:
        """Return all discovered tools across all connected servers."""
        result: list[McpToolAdapter] = []
        for client in self._clients.values():
            result.extend(client.tools)
        return result

    def get_client(self, name: str) -> McpClient | None:
        return self._clients.get(name)

    def list_servers(self) -> list[str]:
        return list(self._clients.keys())

    def __len__(self) -> int:
        return len(self._clients)

    def __contains__(self, name: str) -> bool:
        return name in self._clients


__all__ = [
    "McpClient",
    "McpServerConfig",
    "McpToolAdapter",
    "McpToolRegistry",
    "McpToolSchema",
    "McpTransport",
    "McpTransportMode",
]
