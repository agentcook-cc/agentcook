"""Transport-layer storage protocols (backend-agnostic).

Three structural protocols separate the *kind* of storage from the
*backend* providing it. Higher-level abstractions in ``agentcook-core``
(``MemoryStoreProtocol``, ``IdentityProtocol`` …) compose these to build
business semantics.

- :class:`SqlStoreProtocol`        — relational backend (PostgreSQL default).
- :class:`KeyValueStoreProtocol`   — KV cache / ephemeral state (Redis default).
- :class:`ObjectStoreProtocol`     — large-binary store (S3 / MinIO default).

All methods are ``async``. Implementations live alongside this module:
``postgres.py`` / ``redis.py`` / ``s3.py``. Each implementation uses
lazy SDK imports so installing only the extras you need is supported
(``pip install agentcook-storage[postgres]``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SqlStoreProtocol(Protocol):
    """Async relational store (asyncpg-shaped surface).

    Methods accept positional parameters using the backend's native
    placeholder syntax (``$1`` for asyncpg). The protocol does not
    attempt to abstract SQL dialect — schema migrations and DDL are
    written against the chosen backend (PostgreSQL + pgvector for v1,
    per ADR-011).
    """

    async def execute(self, query: str, *args: Any) -> str:
        """Run a write statement; return backend status string."""

    async def fetch(self, query: str, *args: Any) -> Sequence[Any]:
        """Run a read statement; return all rows as a sequence."""

    async def fetchrow(self, query: str, *args: Any) -> Any | None:
        """Return the first row, or ``None`` if no rows match."""

    async def close(self) -> None:
        """Release the underlying connection pool."""


@runtime_checkable
class KeyValueStoreProtocol(Protocol):
    """Async key-value store (Redis-shaped surface)."""

    async def get(self, key: str) -> str | None:
        """Return the value for *key*, or ``None`` if absent."""

    async def set(
        self,
        key: str,
        value: str,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        """Set *key* to *value*, optionally with a TTL."""

    async def delete(self, key: str) -> int:
        """Delete *key*; return number of keys removed (0 or 1)."""

    async def close(self) -> None:
        """Release the client / connection pool."""


@runtime_checkable
class ObjectStoreProtocol(Protocol):
    """Async S3-compatible object store (boto3-shaped surface).

    Uses S3 vocabulary (bucket / key / presigned URL) deliberately —
    99% of teams writing agent files target an S3 wire-compatible
    backend (AWS S3, MinIO, Cloudflare R2, Alibaba OSS in compat mode).
    """

    async def put_object(self, bucket: str, key: str, body: bytes) -> None:
        """Upload *body* to ``s3://{bucket}/{key}``."""

    async def get_object(self, bucket: str, key: str) -> bytes:
        """Download the object; raise on missing keys."""

    async def delete_object(self, bucket: str, key: str) -> None:
        """Best-effort delete; idempotent."""

    async def list_objects(self, bucket: str, prefix: str = "") -> AsyncIterator[str]:
        """Yield object keys matching *prefix*, paginated by the backend."""

    async def presigned_url(self, bucket: str, key: str, *, expires_in: int = 3600) -> str:
        """Return a time-limited GET URL for sharing without auth."""


__all__ = [
    "KeyValueStoreProtocol",
    "ObjectStoreProtocol",
    "SqlStoreProtocol",
]
