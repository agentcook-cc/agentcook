"""Connector runtime: manage connector lifecycle + adapter implementations.

Adapters translate the declarative :class:`ConnectorConfig` (from
``connectors.json``) into live connections. Each adapter flavour
(:class:`OAuthAdapter`, :class:`HttpAdapter`, :class:`McpAdapter`,
:class:`WebhookAdapter`) satisfies :class:`ConnectorProtocol` and
adds flavour-specific lifecycle (token refresh, SSE subscription, etc.).

Design decisions:
- **Async-first**: all I/O methods are ``async``.
- **stdlib-only at the core layer**: adapters define the *shape* but
  concrete HTTP calls require an injected transport (``httpx`` in the
  main shell). This keeps agentcook-core dependency-free.
- **ConnectorManager** owns the open/close lifecycle for a set of
  connectors and exposes a unified tool-surface to the Agent.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from agentcook_core.protocols import ConnectorProtocol, ToolProtocol
from agentcook_core.types import ConnectorConfig, ConnectorKind, ToolResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTTP transport protocol (injected, not owned)
# ---------------------------------------------------------------------------

@runtime_checkable
class HttpTransport(Protocol):
    """Minimal async HTTP client shape (matches ``httpx.AsyncClient``)."""

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        timeout: float | None = None,
    ) -> Any: ...


# ---------------------------------------------------------------------------
# OAuth token store protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class OAuthTokenStore(Protocol):
    """Persist and retrieve OAuth tokens for a connector."""

    async def get_token(self, connector_name: str) -> dict[str, Any] | None: ...
    async def save_token(self, connector_name: str, token: dict[str, Any]) -> None: ...


# ---------------------------------------------------------------------------
# Base adapter with shared lifecycle
# ---------------------------------------------------------------------------

@dataclass
class BaseAdapter:
    """Shared state for all connector adapters."""

    _config: ConnectorConfig
    _opened: bool = field(default=False, repr=False)

    @property
    def config(self) -> ConnectorConfig:
        return self._config

    async def close(self) -> None:
        self._opened = False

    async def tools(self) -> Sequence[ToolProtocol]:
        return ()


# ---------------------------------------------------------------------------
# OAuthAdapter
# ---------------------------------------------------------------------------

@dataclass
class OAuthAdapter(BaseAdapter):
    """OAuth 2.0 connector adapter.

    Handles the authorization-code / client-credentials flow lifecycle.
    The actual HTTP calls require an injected :class:`HttpTransport` and
    :class:`OAuthTokenStore`; this adapter orchestrates the flow shape.

    Note: the real OAuth redirect / callback flow lives in the Java
    business backend (ADR-013). This adapter is the *Python runtime's*
    client-side token consumer — it refreshes tokens and injects them
    into outbound API calls.
    """

    _http: HttpTransport | None = field(default=None, repr=False)
    _token_store: OAuthTokenStore | None = field(default=None, repr=False)

    async def open(self) -> None:
        if self._opened:
            return
        if self._token_store is None:
            raise RuntimeError(
                f"OAuthAdapter({self._config.name!r}) requires a token store"
            )
        token = await self._token_store.get_token(self._config.name)
        if token and _is_token_expired(token):
            token = await self._refresh_token(token)
        self._opened = True
        logger.info("OAuthAdapter(%s) opened", self._config.name)

    async def _refresh_token(self, token: dict[str, Any]) -> dict[str, Any]:
        """Refresh an expired OAuth token using the refresh_token grant."""
        if self._http is None:
            raise RuntimeError("HttpTransport not injected")
        refresh_url = self._config.config.get("token_url", "")
        if not refresh_url:
            raise RuntimeError(
                f"OAuthAdapter({self._config.name!r}): no token_url in config"
            )
        response = await self._http.request(
            "POST",
            refresh_url,
            json={
                "grant_type": "refresh_token",
                "refresh_token": token.get("refresh_token", ""),
                "client_id": self._config.config.get("client_id", ""),
            },
        )
        new_token = response if isinstance(response, dict) else {}
        if self._token_store:
            await self._token_store.save_token(self._config.name, new_token)
        return new_token


def _is_token_expired(token: dict[str, Any]) -> bool:
    """Check if an OAuth token dict has expired (best-effort)."""
    import time
    expires_at = token.get("expires_at", 0)
    if not expires_at:
        return False
    return time.time() > float(expires_at)


# ---------------------------------------------------------------------------
# HttpAdapter
# ---------------------------------------------------------------------------

@dataclass
class HttpAdapter(BaseAdapter):
    """Plain HTTP API connector (no auth flow — uses static headers)."""

    _http: HttpTransport | None = field(default=None, repr=False)

    async def open(self) -> None:
        if self._opened:
            return
        self._opened = True
        logger.info("HttpAdapter(%s) opened", self._config.name)


# ---------------------------------------------------------------------------
# McpAdapter
# ---------------------------------------------------------------------------

@dataclass
class McpAdapter(BaseAdapter):
    """MCP (Model Context Protocol) connector adapter.

    Connects to an MCP server and exposes its tools as
    :class:`ToolProtocol` instances. The actual MCP client transport
    is injected; this adapter defines the lifecycle shape.
    """

    _mcp_tools: list[ToolProtocol] = field(default_factory=list, repr=False)

    async def open(self) -> None:
        if self._opened:
            return
        # Phase 2 Day 20: mcp_adapter module will wire the real MCP client.
        # For now the adapter opens successfully but exposes 0 tools until
        # the MCP handshake is implemented.
        self._opened = True
        logger.info("McpAdapter(%s) opened (tools: %d)", self._config.name, len(self._mcp_tools))

    async def tools(self) -> Sequence[ToolProtocol]:
        return list(self._mcp_tools)


# ---------------------------------------------------------------------------
# WebhookAdapter
# ---------------------------------------------------------------------------

@dataclass
class WebhookAdapter(BaseAdapter):
    """Webhook / IM event-callback connector (DingTalk / Lark / Slack).

    Receives inbound events via a registered callback URL. The adapter
    validates signatures and dispatches to the Agent's event handler.
    """

    async def open(self) -> None:
        if self._opened:
            return
        self._opened = True
        logger.info("WebhookAdapter(%s) opened", self._config.name)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_ADAPTER_MAP: dict[ConnectorKind, type[BaseAdapter]] = {
    ConnectorKind.OAUTH: OAuthAdapter,
    ConnectorKind.HTTP: HttpAdapter,
    ConnectorKind.MCP: McpAdapter,
    ConnectorKind.WEBHOOK: WebhookAdapter,
    ConnectorKind.CUSTOM: HttpAdapter,  # fallback
}


def create_connector(
    config: ConnectorConfig,
    *,
    http: HttpTransport | None = None,
    token_store: OAuthTokenStore | None = None,
) -> BaseAdapter:
    """Factory: build the right adapter from a :class:`ConnectorConfig`."""
    adapter_cls = _ADAPTER_MAP.get(config.kind, HttpAdapter)
    if adapter_cls is OAuthAdapter:
        return OAuthAdapter(_config=config, _http=http, _token_store=token_store)
    if adapter_cls is HttpAdapter:
        return HttpAdapter(_config=config, _http=http)
    if adapter_cls is McpAdapter:
        return McpAdapter(_config=config)
    return adapter_cls(_config=config)


# ---------------------------------------------------------------------------
# ConnectorManager
# ---------------------------------------------------------------------------

class ConnectorManager:
    """Lifecycle manager for a set of connectors.

    Owns open/close ordering and exposes the unified tool surface
    (all tools from all connectors merged).
    """

    def __init__(self) -> None:
        self._connectors: dict[str, BaseAdapter] = {}

    def add(self, adapter: BaseAdapter) -> None:
        name = adapter.config.name
        if name in self._connectors:
            raise ValueError(f"Connector {name!r} already registered")
        self._connectors[name] = adapter

    async def open_all(self) -> None:
        for name, connector in self._connectors.items():
            try:
                await connector.open()
            except Exception:
                logger.exception("Failed to open connector %s", name)

    async def close_all(self) -> None:
        for connector in self._connectors.values():
            try:
                await connector.close()
            except Exception:
                logger.exception("Failed to close connector %s", connector.config.name)

    async def all_tools(self) -> list[ToolProtocol]:
        """Collect tools from all open connectors."""
        result: list[ToolProtocol] = []
        for connector in self._connectors.values():
            result.extend(await connector.tools())
        return result

    def get(self, name: str) -> BaseAdapter | None:
        return self._connectors.get(name)

    def list_connectors(self) -> Sequence[BaseAdapter]:
        return list(self._connectors.values())

    def __len__(self) -> int:
        return len(self._connectors)

    def __contains__(self, name: str) -> bool:
        return name in self._connectors


__all__ = [
    "BaseAdapter",
    "ConnectorManager",
    "HttpAdapter",
    "HttpTransport",
    "McpAdapter",
    "OAuthAdapter",
    "OAuthTokenStore",
    "WebhookAdapter",
    "create_connector",
]
