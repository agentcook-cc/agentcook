"""PostgreSQL + pgvector adapter implementing :class:`SqlStoreProtocol`.

Per ADR-011 the v1 vector backend is pgvector running inside the same
PostgreSQL instance — no separate vector service. This module exposes
two surfaces:

- :class:`PostgresStore` — thin asyncpg pool wrapper satisfying
  :class:`SqlStoreProtocol`. Knows nothing about pgvector specifically;
  callers issue ``CREATE EXTENSION vector`` / vector queries through
  ``execute`` / ``fetch`` like any other DDL.
- :func:`ensure_pgvector_extension` — idempotent ``CREATE EXTENSION IF
  NOT EXISTS vector`` helper, intended to be called once at startup or
  during alembic migrations.

The asyncpg SDK is lazily imported so ``pip install agentcook-storage``
without the ``[postgres]`` extra still lets you import this module's
*types* (useful for typing in tests / annotations that don't construct
a pool).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import asyncpg


class PostgresStore:
    """Async PostgreSQL store backed by an asyncpg connection pool."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @classmethod
    async def connect(
        cls,
        dsn: str,
        *,
        min_size: int = 1,
        max_size: int = 10,
        **pool_kwargs: Any,
    ) -> PostgresStore:
        """Create a new store with a freshly-built asyncpg pool."""
        try:
            import asyncpg
        except ImportError as exc:
            raise ImportError(
                "Install agentcook-storage[postgres] to use PostgresStore."
            ) from exc
        pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=min_size,
            max_size=max_size,
            **pool_kwargs,
        )
        if pool is None:  # pragma: no cover — asyncpg returns None only on bad config
            raise RuntimeError(f"asyncpg failed to create pool for {dsn!r}")
        return cls(pool)

    async def execute(self, query: str, *args: Any) -> str:
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> Sequence[Any]:
        async with self._pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> Any | None:
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def close(self) -> None:
        await self._pool.close()


async def ensure_pgvector_extension(store: PostgresStore) -> None:
    """Idempotently create the ``vector`` extension.

    Call this once at app startup. The DDL is wrapped in ``IF NOT
    EXISTS`` so it is safe to run on every boot. The connecting role
    must have ``CREATE`` on the database (Postgres superuser or a role
    granted ``CREATE`` explicitly).
    """
    await store.execute("CREATE EXTENSION IF NOT EXISTS vector")


__all__ = ["PostgresStore", "ensure_pgvector_extension"]
