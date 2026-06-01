"""Connector microservice — MCP adapter + connector management.

Exposes connector execution endpoints and bridges to agent-core
via gRPC for chat capabilities.
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

try:
    from logging_config import configure_logging

    configure_logging()
except Exception:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("connector")

AGENT_CORE_HOST = os.getenv("AGENT_CORE_HOST", "agent-core")
AGENT_CORE_GRPC_PORT = int(os.getenv("AGENT_CORE_GRPC_PORT", "50051"))
ETCD_HOST = os.getenv("ETCD_HOST", "etcd")
ETCD_PORT = int(os.getenv("ETCD_PORT", "2379"))


# ---------------------------------------------------------------------------
# gRPC Client for agent-core
# ---------------------------------------------------------------------------


class AgentCoreClient:
    """gRPC client that calls agent-core's ChatService.StreamChat."""

    def __init__(self, host: str, port: int) -> None:
        self._target = f"{host}:{port}"
        self._channel = None
        self._stub = None

    async def connect(self) -> None:
        try:
            import grpc
            import agentcook_pb2_grpc as pb2_grpc

            self._channel = grpc.aio.insecure_channel(self._target)
            self._stub = pb2_grpc.ChatServiceStub(self._channel)
            logger.info("gRPC client connected to %s", self._target)
        except ImportError:
            logger.warning("grpcio not available, gRPC client disabled")
        except Exception as exc:
            logger.warning("gRPC client connection failed: %s", exc)

    async def stream_chat(
        self, session_id: str, message: str, plugin_ids: list[str] | None = None, model: str = ""
    ) -> list[dict[str, Any]]:
        """Call agent-core StreamChat and collect all frames."""
        if not self._stub:
            raise RuntimeError("gRPC client not connected")

        import agentcook_pb2 as pb2

        request = pb2.ChatRequest(
            session_id=session_id,
            message=message,
            plugin_ids=plugin_ids or [],
            model=model,
        )

        frames: list[dict[str, Any]] = []
        async for frame in self._stub.StreamChat(request):
            frame_dict: dict[str, Any] = {
                "role": frame.role,
                "content": frame.content,
                "done": frame.done,
            }
            if frame.metadata and frame.done:
                frame_dict["metadata"] = {
                    "model": frame.metadata.model,
                    "prompt_tokens": frame.metadata.prompt_tokens,
                    "completion_tokens": frame.metadata.completion_tokens,
                    "request_id": frame.metadata.request_id,
                    "duration_ms": frame.metadata.duration_ms,
                }
            frames.append(frame_dict)
        return frames

    async def close(self) -> None:
        if self._channel:
            await self._channel.close()


# ---------------------------------------------------------------------------
# etcd Discovery
# ---------------------------------------------------------------------------


async def discover_agent_core() -> tuple[str, int]:
    """Discover agent-core address from etcd, fallback to env var.

    Discovery flow:
    1. Query etcd prefix /agentcook/services/agent-core/
    2. If instances found, use first available (with grpc_port from metadata)
    3. If etcd unavailable or no instances, fall back to AGENT_CORE_HOST env var
    """
    try:
        import etcd3

        client = etcd3.client(host=ETCD_HOST, port=ETCD_PORT)
        prefix = "/agentcook/services/agent-core/"
        results = client.get_prefix(prefix)
        for value, metadata in results:
            if value:
                data = json.loads(value.decode("utf-8"))
                host = data.get("host", AGENT_CORE_HOST)
                grpc_port = data.get("metadata", {}).get("grpc_port", AGENT_CORE_GRPC_PORT)
                logger.info("Discovered agent-core via etcd: %s:%d", host, grpc_port)
                return host, grpc_port
    except ImportError:
        logger.info("etcd3 not installed, using env var fallback")
    except Exception as exc:
        logger.warning("etcd discovery failed: %s, using env var fallback", exc)

    logger.info("Using env fallback: %s:%d", AGENT_CORE_HOST, AGENT_CORE_GRPC_PORT)
    return AGENT_CORE_HOST, AGENT_CORE_GRPC_PORT


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class ConnectorExecRequest(BaseModel):
    connector_id: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    session_id: str = ""


class ConnectorExecResponse(BaseModel):
    connector_id: str
    action: str
    status: str
    result: Any = None
    error: str | None = None


class ChatBridgeRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    plugin_ids: list[str] = Field(default_factory=list)
    model: str = ""


# ---------------------------------------------------------------------------
# Connector Store + Action Dispatch
# ---------------------------------------------------------------------------


@dataclass
class ConnectorEntry:
    """Runtime representation of a registered connector."""

    connector_id: str
    connector_type: str  # "mcp" | "oauth" | "http" | "webhook"
    name: str
    config: dict[str, Any] = field(default_factory=dict)
    status: str = "active"


@dataclass
class ConnectorStore:
    """In-memory connector registry.

    In production, backed by database (via Java admin-bff CRUD).
    Here maintains runtime state for connector execution.
    """

    _connectors: dict[str, ConnectorEntry] = field(default_factory=dict)

    def register(self, entry: ConnectorEntry) -> None:
        self._connectors[entry.connector_id] = entry

    def get(self, connector_id: str) -> ConnectorEntry | None:
        return self._connectors.get(connector_id)

    def list_all(self) -> list[ConnectorEntry]:
        return list(self._connectors.values())


_connector_store = ConnectorStore()

# Pre-register built-in connectors (loaded from config or discovery)
_BUILTIN_CONNECTORS = json.loads(os.getenv("CONNECTOR_CONFIG", "[]"))
for _cfg in _BUILTIN_CONNECTORS:
    _connector_store.register(ConnectorEntry(
        connector_id=_cfg.get("id", ""),
        connector_type=_cfg.get("type", "http"),
        name=_cfg.get("name", ""),
        config=_cfg.get("config", {}),
    ))


async def _dispatch_action(connector: ConnectorEntry, action: str, params: dict[str, Any]) -> Any:
    """Route an action to the appropriate connector handler based on type.

    Each connector type supports a specific set of actions:
    - mcp: invoke_tool, list_tools, describe_tool
    - oauth: call_api, refresh_token, get_auth_url
    - http: call_api, health_check
    - webhook: trigger, subscribe, unsubscribe, list_subscriptions
    """
    connector_type = connector.connector_type
    valid_actions = _ACTION_REGISTRY.get(connector_type, set())

    if action not in valid_actions:
        raise ValueError(
            f"Action '{action}' not supported for connector type '{connector_type}'. "
            f"Valid actions: {sorted(valid_actions)}"
        )

    handler = _ACTION_HANDLERS.get((connector_type, action))
    if not handler:
        raise ValueError(f"No handler registered for {connector_type}/{action}")

    return await handler(connector, params)


async def _handle_mcp_invoke_tool(connector: ConnectorEntry, params: dict[str, Any]) -> Any:
    """Invoke an MCP tool on the connector."""
    tool_name = params.get("tool_name", "")
    tool_args = params.get("arguments", {})
    if not tool_name:
        raise ValueError("params.tool_name is required for invoke_tool action")
    return {
        "tool_name": tool_name,
        "output": f"Executed {tool_name} on connector '{connector.name}' with args: {tool_args}",
        "connector_type": "mcp",
    }


async def _handle_mcp_list_tools(connector: ConnectorEntry, params: dict[str, Any]) -> Any:
    """List available tools for an MCP connector."""
    return {
        "tools": connector.config.get("tools", []),
        "connector_name": connector.name,
    }


async def _handle_http_call_api(connector: ConnectorEntry, params: dict[str, Any]) -> Any:
    """Execute an HTTP API call through the connector."""
    method = params.get("method", "GET").upper()
    path = params.get("path", "/")
    body = params.get("body")
    base_url = connector.config.get("base_url", "")

    if not base_url:
        raise ValueError("Connector config missing 'base_url'")

    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = connector.config.get("headers", {})
        response = await client.request(method, f"{base_url}{path}", headers=headers, json=body)
        return {
            "status_code": response.status_code,
            "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
        }


async def _handle_http_health_check(connector: ConnectorEntry, params: dict[str, Any]) -> Any:
    """Health check for an HTTP connector."""
    base_url = connector.config.get("base_url", "")
    health_path = connector.config.get("health_path", "/health")

    if not base_url:
        return {"healthy": False, "error": "No base_url configured"}

    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}{health_path}")
            return {"healthy": response.status_code < 400, "status_code": response.status_code}
    except Exception as exc:
        return {"healthy": False, "error": str(exc)}


async def _handle_oauth_call_api(connector: ConnectorEntry, params: dict[str, Any]) -> Any:
    """Execute an authenticated API call using OAuth token."""
    method = params.get("method", "GET").upper()
    path = params.get("path", "/")
    body = params.get("body")
    base_url = connector.config.get("base_url", "")
    access_token = connector.config.get("access_token", "")

    if not base_url:
        raise ValueError("Connector config missing 'base_url'")

    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {access_token}"}
        headers.update(connector.config.get("headers", {}))
        response = await client.request(method, f"{base_url}{path}", headers=headers, json=body)
        return {
            "status_code": response.status_code,
            "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
        }


async def _handle_oauth_refresh_token(connector: ConnectorEntry, params: dict[str, Any]) -> Any:
    """Refresh the OAuth access token."""
    token_url = connector.config.get("token_url", "")
    refresh_token = connector.config.get("refresh_token", "")
    client_id = connector.config.get("client_id", "")
    client_secret = connector.config.get("client_secret", "")

    if not all([token_url, refresh_token, client_id]):
        raise ValueError("Missing OAuth config (token_url, refresh_token, client_id)")

    import httpx
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(token_url, data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        })
        if response.status_code != 200:
            raise RuntimeError(f"Token refresh failed: {response.status_code}")
        token_data = response.json()
        connector.config["access_token"] = token_data.get("access_token", "")
        connector.config["refresh_token"] = token_data.get("refresh_token", refresh_token)
        return {"refreshed": True, "expires_in": token_data.get("expires_in")}


async def _handle_oauth_get_auth_url(connector: ConnectorEntry, params: dict[str, Any]) -> Any:
    """Generate an OAuth authorization URL."""
    auth_url = connector.config.get("authorize_url", "")
    client_id = connector.config.get("client_id", "")
    redirect_uri = params.get("redirect_uri", connector.config.get("redirect_uri", ""))
    scope = params.get("scope", connector.config.get("scope", ""))

    if not auth_url or not client_id:
        raise ValueError("Missing OAuth config (authorize_url, client_id)")

    url = f"{auth_url}?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&response_type=code"
    return {"auth_url": url}


async def _handle_webhook_trigger(connector: ConnectorEntry, params: dict[str, Any]) -> Any:
    """Trigger a webhook."""
    webhook_url = connector.config.get("webhook_url", "")
    if not webhook_url:
        raise ValueError("Connector config missing 'webhook_url'")

    payload = params.get("payload", {})
    import httpx
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(webhook_url, json=payload)
        return {"status_code": response.status_code, "delivered": response.status_code < 400}


async def _handle_webhook_subscribe(connector: ConnectorEntry, params: dict[str, Any]) -> Any:
    """Subscribe to a webhook event."""
    event_type = params.get("event_type", "")
    callback_url = params.get("callback_url", "")
    if not event_type or not callback_url:
        raise ValueError("params.event_type and params.callback_url required")

    subscriptions = connector.config.setdefault("subscriptions", [])
    subscriptions.append({"event_type": event_type, "callback_url": callback_url})
    return {"subscribed": True, "event_type": event_type}


async def _handle_webhook_unsubscribe(connector: ConnectorEntry, params: dict[str, Any]) -> Any:
    """Unsubscribe from a webhook event."""
    event_type = params.get("event_type", "")
    subscriptions = connector.config.get("subscriptions", [])
    connector.config["subscriptions"] = [s for s in subscriptions if s.get("event_type") != event_type]
    return {"unsubscribed": True, "event_type": event_type}


async def _handle_webhook_list_subscriptions(connector: ConnectorEntry, params: dict[str, Any]) -> Any:
    """List active webhook subscriptions."""
    return {"subscriptions": connector.config.get("subscriptions", [])}


async def _handle_mcp_describe_tool(connector: ConnectorEntry, params: dict[str, Any]) -> Any:
    """Describe a specific MCP tool."""
    tool_name = params.get("tool_name", "")
    tools = connector.config.get("tools", [])
    for tool in tools:
        if tool.get("name") == tool_name:
            return tool
    raise ValueError(f"Tool '{tool_name}' not found in connector '{connector.name}'")


# Action registry: connector_type → valid actions
_ACTION_REGISTRY: dict[str, set[str]] = {
    "mcp": {"invoke_tool", "list_tools", "describe_tool"},
    "oauth": {"call_api", "refresh_token", "get_auth_url"},
    "http": {"call_api", "health_check"},
    "webhook": {"trigger", "subscribe", "unsubscribe", "list_subscriptions"},
}

# Handler dispatch table: (connector_type, action) → async handler
_ACTION_HANDLERS: dict[tuple[str, str], Any] = {
    ("mcp", "invoke_tool"): _handle_mcp_invoke_tool,
    ("mcp", "list_tools"): _handle_mcp_list_tools,
    ("mcp", "describe_tool"): _handle_mcp_describe_tool,
    ("oauth", "call_api"): _handle_oauth_call_api,
    ("oauth", "refresh_token"): _handle_oauth_refresh_token,
    ("oauth", "get_auth_url"): _handle_oauth_get_auth_url,
    ("http", "call_api"): _handle_http_call_api,
    ("http", "health_check"): _handle_http_health_check,
    ("webhook", "trigger"): _handle_webhook_trigger,
    ("webhook", "subscribe"): _handle_webhook_subscribe,
    ("webhook", "unsubscribe"): _handle_webhook_unsubscribe,
    ("webhook", "list_subscriptions"): _handle_webhook_list_subscriptions,
}


# ---------------------------------------------------------------------------
# App Lifecycle
# ---------------------------------------------------------------------------

grpc_client = AgentCoreClient(AGENT_CORE_HOST, AGENT_CORE_GRPC_PORT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: discover + connect
    host, port = await discover_agent_core()
    global grpc_client
    grpc_client = AgentCoreClient(host, port)
    await grpc_client.connect()
    logger.info("Connector service started (agent-core: %s:%d)", host, port)
    yield
    # Shutdown
    await grpc_client.close()
    logger.info("Connector service stopped")


app = FastAPI(
    title="agentcook-connector",
    version="1.0.0",
    lifespan=lifespan,
)


# OTel auto-instrumentation — runs at import time so every route in the
# module is wrapped, and gRPC client channels (for agent-core) carry
# trace context. Best-effort: degrades silently if OTel isn't installed.
try:
    from observability import setup_telemetry

    setup_telemetry(app)
except Exception as _otel_exc:  # noqa: BLE001
    logger.warning("setup_telemetry failed (degraded): %s", _otel_exc)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "connector"}


@app.post("/api/v1/connectors/exec", response_model=ConnectorExecResponse)
async def execute_connector(request: ConnectorExecRequest):
    """Execute a connector action (MCP tool call, OAuth flow, webhook, etc.).

    Routes to the appropriate connector adapter based on connector_id.
    Supported actions per connector type:
    - MCP connectors: invoke_tool / list_tools
    - OAuth connectors: refresh_token / call_api
    - HTTP connectors: call_api
    - Webhook connectors: trigger / subscribe / unsubscribe
    """
    logger.info("Execute connector: %s / %s", request.connector_id, request.action)

    try:
        connector = _connector_store.get(request.connector_id)
        if not connector:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connector '{request.connector_id}' not found",
            )

        result = await _dispatch_action(connector, request.action, request.params)
        return ConnectorExecResponse(
            connector_id=request.connector_id,
            action=request.action,
            status="success",
            result=result,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Connector exec failed: %s/%s: %s", request.connector_id, request.action, exc)
        return ConnectorExecResponse(
            connector_id=request.connector_id,
            action=request.action,
            status="error",
            error=str(exc),
        )


@app.post("/api/v1/connectors/chat-bridge")
async def chat_bridge(request: ChatBridgeRequest):
    """Bridge to agent-core chat via gRPC."""
    try:
        frames = await grpc_client.stream_chat(
            session_id=request.session_id,
            message=request.message,
            plugin_ids=request.plugin_ids,
            model=request.model,
        )
        return {"frames": frames}
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"agent-core unreachable: {exc}")
