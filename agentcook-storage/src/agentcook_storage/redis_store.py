"""Redis adapter implementing :class:`KeyValueStoreProtocol`.

Wraps ``redis.asyncio.Redis`` with the agentcook KV surface. Module name
is ``redis_store`` (not ``redis``) to avoid shadowing the upstream
``redis`` package when this module is imported alongside it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from redis.asyncio import Redis


class RedisStore:
    """Async Redis store satisfying :class:`KeyValueStoreProtocol`."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    @classmethod
    def from_url(cls, url: str, **client_kwargs: Any) -> RedisStore:
        """Build a store from a ``redis://host:port/db`` URL."""
        try:
            from redis.asyncio import Redis
        except ImportError as exc:
            raise ImportError(
                "Install agentcook-storage[redis] to use RedisStore."
            ) from exc
        client = Redis.from_url(url, decode_responses=True, **client_kwargs)
        return cls(client)

    async def get(self, key: str) -> str | None:
        return await self._client.get(key)

    async def set(
        self,
        key: str,
        value: str,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        if ttl_seconds is not None:
            await self._client.set(key, value, ex=ttl_seconds)
        else:
            await self._client.set(key, value)

    async def delete(self, key: str) -> int:
        return int(await self._client.delete(key))

    async def close(self) -> None:
        await self._client.aclose()


__all__ = ["RedisStore"]
