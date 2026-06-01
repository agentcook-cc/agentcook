"""etcd service discovery client for agentcook microservices.

Provides service registration, discovery, and watch capabilities
backed by etcd v3. Falls back gracefully when etcd is unavailable.

Key format: /agentcook/services/{service_name}/{instance_id}
Value: JSON {"host": "...", "port": 8000, "metadata": {...}}
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

SERVICE_PREFIX = "/agentcook/services"
DEFAULT_TTL = 30  # seconds
KEEPALIVE_INTERVAL = 10  # seconds


@dataclass(frozen=True, slots=True)
class ServiceInstance:
    """Represents a discovered service instance."""

    service_name: str
    instance_id: str
    host: str
    port: int
    metadata: dict[str, Any] = field(default_factory=dict)
    registered_at: float = 0.0

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"

    def to_json(self) -> str:
        return json.dumps({
            "host": self.host,
            "port": self.port,
            "metadata": self.metadata,
            "registered_at": self.registered_at,
        })

    @classmethod
    def from_json(cls, service_name: str, instance_id: str, raw: str) -> ServiceInstance:
        data = json.loads(raw)
        return cls(
            service_name=service_name,
            instance_id=instance_id,
            host=data["host"],
            port=data["port"],
            metadata=data.get("metadata", {}),
            registered_at=data.get("registered_at", 0.0),
        )


@runtime_checkable
class ServiceRegistry(Protocol):
    """Protocol for service registration and discovery."""

    async def register(
        self, service_name: str, instance_id: str, host: str, port: int, metadata: dict[str, Any] | None = None
    ) -> None: ...

    async def deregister(self, service_name: str, instance_id: str) -> None: ...

    async def discover(self, service_name: str) -> list[ServiceInstance]: ...


class EtcdServiceRegistry:
    """etcd-backed service registry with lease-based TTL and keepalive.

    Features:
    - Register with 30s TTL lease + automatic keepalive
    - Discover all instances of a service via prefix query
    - Graceful degradation: falls back to env var when etcd unavailable
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 2379,
        ttl: int = DEFAULT_TTL,
        keepalive_interval: int = KEEPALIVE_INTERVAL,
    ) -> None:
        self._host = host
        self._port = port
        self._ttl = ttl
        self._keepalive_interval = keepalive_interval
        self._client: Any = None
        self._lease: Any = None
        self._keepalive_task: asyncio.Task | None = None
        self._registered_key: str | None = None

    async def _get_client(self) -> Any:
        """Lazy-init etcd client."""
        if self._client is None:
            try:
                import etcd3
                self._client = etcd3.client(host=self._host, port=self._port)
            except ImportError:
                logger.warning("etcd3 package not installed, using stub mode")
                self._client = _StubEtcdClient()
            except Exception as exc:
                logger.warning("Cannot connect to etcd at %s:%d: %s", self._host, self._port, exc)
                self._client = _StubEtcdClient()
        return self._client

    async def register(
        self,
        service_name: str,
        instance_id: str,
        host: str,
        port: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Register this instance with etcd using a TTL lease."""
        client = await self._get_client()
        key = f"{SERVICE_PREFIX}/{service_name}/{instance_id}"
        instance = ServiceInstance(
            service_name=service_name,
            instance_id=instance_id,
            host=host,
            port=port,
            metadata=metadata or {},
            registered_at=time.time(),
        )
        value = instance.to_json()

        try:
            if isinstance(client, _StubEtcdClient):
                client.put(key, value)
                logger.info("Registered (stub): %s", key)
            else:
                lease = client.lease(self._ttl)
                client.put(key, value, lease=lease)
                self._lease = lease
                self._registered_key = key
                self._keepalive_task = asyncio.create_task(self._keepalive_loop(lease))
                logger.info("Registered with etcd: %s (TTL=%ds)", key, self._ttl)
        except Exception as exc:
            logger.warning("etcd registration failed: %s (service runs without discovery)", exc)

    async def deregister(self, service_name: str, instance_id: str) -> None:
        """Remove this instance from etcd."""
        client = await self._get_client()
        key = f"{SERVICE_PREFIX}/{service_name}/{instance_id}"

        if self._keepalive_task:
            self._keepalive_task.cancel()
            self._keepalive_task = None

        try:
            client.delete(key)
            logger.info("Deregistered: %s", key)
        except Exception as exc:
            logger.warning("etcd deregister failed: %s", exc)

    async def discover(self, service_name: str) -> list[ServiceInstance]:
        """Discover all instances of a service.

        Falls back to AGENT_CORE_HOST env var if etcd is unavailable.
        """
        client = await self._get_client()
        prefix = f"{SERVICE_PREFIX}/{service_name}/"
        instances: list[ServiceInstance] = []

        try:
            if isinstance(client, _StubEtcdClient):
                for key, value in client.get_prefix(prefix):
                    instance_id = key.split("/")[-1]
                    instances.append(ServiceInstance.from_json(service_name, instance_id, value))
            else:
                results = client.get_prefix(prefix)
                for value, metadata in results:
                    if value:
                        key = metadata.key.decode("utf-8")
                        instance_id = key.split("/")[-1]
                        instances.append(
                            ServiceInstance.from_json(service_name, instance_id, value.decode("utf-8"))
                        )
        except Exception as exc:
            logger.warning("etcd discover failed: %s, using fallback", exc)

        # Fallback to environment variable
        if not instances:
            instances = self._fallback_discover(service_name)

        return instances

    def _fallback_discover(self, service_name: str) -> list[ServiceInstance]:
        """Fallback discovery using environment variables."""
        env_key = f"{service_name.upper().replace('-', '_')}_HOST"
        host = os.getenv(env_key, "")
        if not host:
            return []

        port_key = f"{service_name.upper().replace('-', '_')}_PORT"
        port = int(os.getenv(port_key, "8000"))
        logger.info("Fallback discovery: %s=%s:%d", service_name, host, port)
        return [
            ServiceInstance(
                service_name=service_name,
                instance_id="fallback",
                host=host,
                port=port,
                metadata={"source": "env_fallback"},
            )
        ]

    async def _keepalive_loop(self, lease: Any) -> None:
        """Periodically refresh the lease to keep registration alive."""
        while True:
            try:
                await asyncio.sleep(self._keepalive_interval)
                lease.refresh()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Lease keepalive failed: %s", exc)
                break


class _StubEtcdClient:
    """In-memory stub when etcd is unavailable (for dev/test)."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def put(self, key: str, value: str, **kwargs) -> None:
        self._store[key] = value

    def get(self, key: str) -> tuple[str | None, Any]:
        return self._store.get(key), None

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def get_prefix(self, prefix: str) -> list[tuple[str, str]]:
        return [(k, v) for k, v in self._store.items() if k.startswith(prefix)]

    def lease(self, ttl: int) -> Any:
        return _StubLease()


class _StubLease:
    def refresh(self) -> None:
        pass


__all__ = [
    "EtcdServiceRegistry",
    "ServiceInstance",
    "ServiceRegistry",
]
