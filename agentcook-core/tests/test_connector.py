"""Tests for agentcook_core.connector."""

from __future__ import annotations

import pytest
from agentcook_core.connector import (
    ConnectorManager,
    HttpAdapter,
    McpAdapter,
    OAuthAdapter,
    WebhookAdapter,
    create_connector,
)
from agentcook_core.types import ConnectorConfig, ConnectorKind

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cfg(name: str = "test", kind: ConnectorKind = ConnectorKind.HTTP) -> ConnectorConfig:
    return ConnectorConfig(name=name, kind=kind, config={})


def _oauth_cfg() -> ConnectorConfig:
    return ConnectorConfig(
        name="gh",
        kind=ConnectorKind.OAUTH,
        config={"client_id": "cid", "token_url": "https://oauth.example.com/token"},
    )


class FakeTokenStore:
    def __init__(self, token: dict | None = None):
        self._tokens: dict[str, dict] = {}
        if token:
            self._tokens["gh"] = token

    async def get_token(self, connector_name: str):
        return self._tokens.get(connector_name)

    async def save_token(self, connector_name: str, token: dict):
        self._tokens[connector_name] = token


class FakeHttp:
    def __init__(self, response: dict | None = None):
        self.calls: list[tuple] = []
        self._response = response or {}

    async def request(self, method, url, *, headers=None, json=None, timeout=None):
        self.calls.append((method, url, json))
        return self._response


# ---------------------------------------------------------------------------
# create_connector factory
# ---------------------------------------------------------------------------

class TestCreateConnector:
    @pytest.mark.unit
    def test_http(self):
        adapter = create_connector(_cfg(kind=ConnectorKind.HTTP))
        assert isinstance(adapter, HttpAdapter)

    @pytest.mark.unit
    def test_oauth(self):
        adapter = create_connector(_oauth_cfg(), token_store=FakeTokenStore())
        assert isinstance(adapter, OAuthAdapter)

    @pytest.mark.unit
    def test_mcp(self):
        adapter = create_connector(_cfg(kind=ConnectorKind.MCP))
        assert isinstance(adapter, McpAdapter)

    @pytest.mark.unit
    def test_webhook(self):
        adapter = create_connector(_cfg(kind=ConnectorKind.WEBHOOK))
        assert isinstance(adapter, WebhookAdapter)

    @pytest.mark.unit
    def test_custom_falls_back_to_http(self):
        adapter = create_connector(_cfg(kind=ConnectorKind.CUSTOM))
        assert isinstance(adapter, HttpAdapter)


# ---------------------------------------------------------------------------
# HttpAdapter
# ---------------------------------------------------------------------------

class TestHttpAdapter:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_open_close(self):
        adapter = HttpAdapter(_config=_cfg())
        assert not adapter._opened
        await adapter.open()
        assert adapter._opened
        await adapter.close()
        assert not adapter._opened

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_tools_empty(self):
        adapter = HttpAdapter(_config=_cfg())
        assert await adapter.tools() == ()


# ---------------------------------------------------------------------------
# OAuthAdapter
# ---------------------------------------------------------------------------

class TestOAuthAdapter:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_open_requires_token_store(self):
        adapter = OAuthAdapter(_config=_oauth_cfg())
        with pytest.raises(RuntimeError, match="requires a token store"):
            await adapter.open()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_open_with_valid_token(self):
        store = FakeTokenStore({"access_token": "tok", "expires_at": 9999999999})
        adapter = OAuthAdapter(_config=_oauth_cfg(), _token_store=store)
        await adapter.open()
        assert adapter._opened

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_open_with_expired_token_refreshes(self):
        store = FakeTokenStore({"access_token": "old", "refresh_token": "rt", "expires_at": 1})
        http = FakeHttp({"access_token": "new", "expires_at": 9999999999})
        adapter = OAuthAdapter(_config=_oauth_cfg(), _http=http, _token_store=store)
        await adapter.open()
        assert adapter._opened
        assert len(http.calls) == 1
        assert http.calls[0][0] == "POST"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_refresh_without_http_raises(self):
        store = FakeTokenStore({"access_token": "old", "refresh_token": "rt", "expires_at": 1})
        adapter = OAuthAdapter(_config=_oauth_cfg(), _token_store=store)
        with pytest.raises(RuntimeError, match="HttpTransport not injected"):
            await adapter.open()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_open_no_token(self):
        store = FakeTokenStore()
        adapter = OAuthAdapter(_config=_oauth_cfg(), _token_store=store)
        await adapter.open()
        assert adapter._opened


# ---------------------------------------------------------------------------
# McpAdapter
# ---------------------------------------------------------------------------

class TestMcpAdapter:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_open_close(self):
        adapter = McpAdapter(_config=_cfg(kind=ConnectorKind.MCP))
        await adapter.open()
        assert adapter._opened
        tools = await adapter.tools()
        assert tools == []
        await adapter.close()
        assert not adapter._opened


# ---------------------------------------------------------------------------
# WebhookAdapter
# ---------------------------------------------------------------------------

class TestWebhookAdapter:
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_open_close(self):
        adapter = WebhookAdapter(_config=_cfg(kind=ConnectorKind.WEBHOOK))
        await adapter.open()
        assert adapter._opened
        await adapter.close()
        assert not adapter._opened


# ---------------------------------------------------------------------------
# ConnectorManager
# ---------------------------------------------------------------------------

class TestConnectorManager:
    @pytest.mark.unit
    def test_add_and_get(self):
        mgr = ConnectorManager()
        adapter = HttpAdapter(_config=_cfg("a"))
        mgr.add(adapter)
        assert len(mgr) == 1
        assert "a" in mgr
        assert mgr.get("a") is adapter

    @pytest.mark.unit
    def test_add_duplicate_raises(self):
        mgr = ConnectorManager()
        mgr.add(HttpAdapter(_config=_cfg("a")))
        with pytest.raises(ValueError, match="already registered"):
            mgr.add(HttpAdapter(_config=_cfg("a")))

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_open_all_close_all(self):
        mgr = ConnectorManager()
        a1 = HttpAdapter(_config=_cfg("a"))
        a2 = McpAdapter(_config=_cfg("b", ConnectorKind.MCP))
        mgr.add(a1)
        mgr.add(a2)
        await mgr.open_all()
        assert a1._opened and a2._opened
        await mgr.close_all()
        assert not a1._opened and not a2._opened

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_all_tools(self):
        mgr = ConnectorManager()
        mgr.add(HttpAdapter(_config=_cfg("a")))
        await mgr.open_all()
        tools = await mgr.all_tools()
        assert tools == []

    @pytest.mark.unit
    def test_list_connectors(self):
        mgr = ConnectorManager()
        mgr.add(HttpAdapter(_config=_cfg("x")))
        mgr.add(McpAdapter(_config=_cfg("y", ConnectorKind.MCP)))
        assert len(mgr.list_connectors()) == 2

    @pytest.mark.unit
    def test_get_missing(self):
        mgr = ConnectorManager()
        assert mgr.get("nope") is None
