"""Unit tests for etcd_registry module."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from etcd_registry import (
    EtcdServiceRegistry,
    ServiceInstance,
    _StubEtcdClient,
)


class TestServiceInstance:
    def test_frozen(self):
        inst = ServiceInstance(service_name="svc", instance_id="i1", host="h", port=8000)
        with pytest.raises(AttributeError):
            inst.host = "other"  # type: ignore[misc]

    def test_address_property(self):
        inst = ServiceInstance(service_name="svc", instance_id="i1", host="10.0.0.1", port=9090)
        assert inst.address == "10.0.0.1:9090"

    def test_to_json_roundtrip(self):
        inst = ServiceInstance(
            service_name="agent-core",
            instance_id="abc",
            host="10.0.0.5",
            port=8000,
            metadata={"grpc_port": 50051},
            registered_at=1000.0,
        )
        raw = inst.to_json()
        parsed = ServiceInstance.from_json("agent-core", "abc", raw)
        assert parsed.host == "10.0.0.5"
        assert parsed.port == 8000
        assert parsed.metadata["grpc_port"] == 50051


class TestStubEtcdClient:
    def test_put_and_get(self):
        client = _StubEtcdClient()
        client.put("/key", "value")
        val, _ = client.get("/key")
        assert val == "value"

    def test_delete(self):
        client = _StubEtcdClient()
        client.put("/key", "value")
        client.delete("/key")
        val, _ = client.get("/key")
        assert val is None

    def test_get_prefix(self):
        client = _StubEtcdClient()
        client.put("/svc/a/1", "v1")
        client.put("/svc/a/2", "v2")
        client.put("/svc/b/1", "v3")
        results = client.get_prefix("/svc/a/")
        assert len(results) == 2


class TestEtcdServiceRegistry:
    @pytest.mark.asyncio
    async def test_register_and_discover_stub_mode(self):
        """When etcd3 is not importable, falls back to stub client."""
        registry = EtcdServiceRegistry(host="nonexistent", port=9999)
        # Force stub client
        registry._client = _StubEtcdClient()

        await registry.register(
            service_name="agent-core",
            instance_id="test-1",
            host="10.0.0.1",
            port=8000,
            metadata={"grpc_port": 50051},
        )

        instances = await registry.discover("agent-core")
        assert len(instances) == 1
        assert instances[0].host == "10.0.0.1"
        assert instances[0].port == 8000
        assert instances[0].metadata["grpc_port"] == 50051

    @pytest.mark.asyncio
    async def test_deregister(self):
        registry = EtcdServiceRegistry()
        registry._client = _StubEtcdClient()

        await registry.register("svc", "i1", "h1", 8000)
        instances = await registry.discover("svc")
        assert len(instances) == 1

        await registry.deregister("svc", "i1")
        instances = await registry.discover("svc")
        assert len(instances) == 0

    @pytest.mark.asyncio
    async def test_discover_fallback_to_env(self, monkeypatch):
        """When no instances in etcd, falls back to env var."""
        registry = EtcdServiceRegistry()
        registry._client = _StubEtcdClient()

        monkeypatch.setenv("AGENT_CORE_HOST", "fallback-host")
        monkeypatch.setenv("AGENT_CORE_PORT", "9000")

        instances = await registry.discover("agent-core")
        assert len(instances) == 1
        assert instances[0].host == "fallback-host"
        assert instances[0].port == 9000
        assert instances[0].metadata["source"] == "env_fallback"

    @pytest.mark.asyncio
    async def test_discover_no_fallback_returns_empty(self, monkeypatch):
        """When no instances and no env var, returns empty list."""
        registry = EtcdServiceRegistry()
        registry._client = _StubEtcdClient()

        monkeypatch.delenv("UNKNOWN_SERVICE_HOST", raising=False)
        instances = await registry.discover("unknown-service")
        assert instances == []
