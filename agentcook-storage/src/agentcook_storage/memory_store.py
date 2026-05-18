"""``MemoryStoreProtocol`` implementations backed by PostgreSQL + pgvector.

This is the **v1 minimal** implementation per ADR-011 — enough to land
``append_event`` + ``search`` so Pact contracts (Day 22) and the admin
Memory browser (B, Day 12+) have a stable surface. Production hardening
(BM25 fusion, ivfflat index tuning, score thresholding, pagination) lands
in Phase 2 Day 22.

Design notes:

- ``PgVectorMemoryStore`` covers only the **event stream** and
  **semantic recall** tiers of :class:`MemoryStoreProtocol`. The
  **session KV** tier raises :class:`NotImplementedError` — that tier
  belongs in Redis (see :class:`RedisStore`); Phase 2 wires the two
  through a composite ``MemoryStore`` facade.

- The embedder is **injected** as a ``Callable`` rather than imported
  from ``agentcook-providers``. This keeps storage free of provider
  dependencies and lets callers swap embedding models (OpenAI 3-small
  default per ADR-011, but Qwen / Zhipu / local bge selectable).

- Vector values are sent as PostgreSQL string literals (``[0.1,0.2,…]``)
  with a ``::vector`` cast. This avoids registering a pgvector codec on
  the shared connection pool — codec registration is a cross-cutting
  side effect that callers shouldn't be surprised by.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime
from typing import Any

from agentcook_core import MemoryEvent, MemoryEventKind, MemoryHit, MemoryRecall

from agentcook_storage.postgres import PostgresStore


def _parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 string into a timezone-aware ``datetime``.

    ``datetime.fromisoformat`` accepts the ``Z`` suffix from Python 3.11+;
    older interpreters would need ``replace('Z', '+00:00')`` — we require
    ``python>=3.11`` so direct call is safe.
    """
    return datetime.fromisoformat(value)

Embedder = Callable[[str], Awaitable[Sequence[float]]]
"""Async callable returning a fixed-dimension embedding for *text*."""


def _format_vector(vec: Sequence[float]) -> str:
    """Render a vector as the pgvector string literal form."""
    return "[" + ",".join(format(float(x), ".7g") for x in vec) + "]"


CREATE_TABLE_SQL = """\
CREATE TABLE IF NOT EXISTS memory_events (
    id          BIGSERIAL PRIMARY KEY,
    agent_id    TEXT NOT NULL,
    timestamp   TIMESTAMPTZ NOT NULL,
    kind        TEXT NOT NULL,
    content     TEXT NOT NULL,
    source      TEXT,
    metadata    JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    embedding   VECTOR({dim})
)
"""

CREATE_INDEX_SQL = """\
CREATE INDEX IF NOT EXISTS memory_events_agent_ts_idx
    ON memory_events (agent_id, timestamp DESC)
"""


class PgVectorMemoryStore:
    """v1 minimal :class:`MemoryStoreProtocol` over PostgreSQL + pgvector."""

    def __init__(
        self,
        store: PostgresStore,
        embedder: Embedder,
        *,
        vector_dim: int = 1536,
    ) -> None:
        self._store = store
        self._embed = embedder
        self._dim = vector_dim

    async def ensure_schema(self) -> None:
        """Idempotently create the events table and supporting index.

        Caller is responsible for ensuring the ``vector`` extension is
        installed first; use :func:`ensure_pgvector_extension`.
        """
        await self._store.execute(CREATE_TABLE_SQL.format(dim=self._dim))
        await self._store.execute(CREATE_INDEX_SQL)

    # ---- session KV (not implemented at this tier) -------------------

    async def remember_session(
        self,
        session_id: str,
        key: str,
        value: Any,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        raise NotImplementedError(
            "Session KV belongs to RedisStore; compose with a session-tier "
            "memory store in Phase 2 (Day 22)."
        )

    async def recall_session(self, session_id: str, key: str) -> Any | None:
        raise NotImplementedError(
            "Session KV belongs to RedisStore; compose with a session-tier "
            "memory store in Phase 2 (Day 22)."
        )

    # ---- event stream -----------------------------------------------

    async def append_event(self, agent_id: str, event: MemoryEvent) -> None:
        vec = await self._embed(event.content)
        await self._store.execute(
            "INSERT INTO memory_events "
            "(agent_id, timestamp, kind, content, source, metadata, embedding) "
            "VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::vector)",
            agent_id,
            _parse_iso(event.timestamp),
            event.kind,
            event.content,
            event.source,
            json.dumps(event.metadata, ensure_ascii=False),
            _format_vector(vec),
        )

    async def stream_events(
        self,
        agent_id: str,
        *,
        since: str | None = None,
        kind: str | None = None,
        limit: int = 100,
    ) -> Sequence[MemoryEvent]:
        clauses: list[str] = ["agent_id = $1"]
        args: list[Any] = [agent_id]
        if since is not None:
            args.append(_parse_iso(since))
            clauses.append(f"timestamp >= ${len(args)}")
        if kind is not None:
            args.append(kind)
            clauses.append(f"kind = ${len(args)}")
        args.append(limit)
        query = (
            "SELECT timestamp, kind, content, source, metadata "
            "FROM memory_events "
            f"WHERE {' AND '.join(clauses)} "
            f"ORDER BY timestamp ASC LIMIT ${len(args)}"
        )
        rows = await self._store.fetch(query, *args)
        return tuple(_row_to_event(r) for r in rows)

    # ---- semantic recall --------------------------------------------

    async def search(
        self,
        agent_id: str,
        query: str,
        *,
        top_k: int = 5,
    ) -> MemoryRecall:
        """v1 cosine-similarity recall over event embeddings.

        Returns ``score = 1 - cosine_distance`` so callers can treat
        higher = more relevant. BM25 fusion (true hybrid) lands Day 22.
        """
        vec = await self._embed(query)
        rows = await self._store.fetch(
            "SELECT timestamp, kind, content, source, metadata, "
            "       1 - (embedding <=> $2::vector) AS score "
            "FROM memory_events "
            "WHERE agent_id = $1 AND embedding IS NOT NULL "
            "ORDER BY embedding <=> $2::vector "
            "LIMIT $3",
            agent_id,
            _format_vector(vec),
            top_k,
        )
        hits = tuple(
            MemoryHit(
                content=row["content"],
                score=float(row["score"]),
                event=_row_to_event(row),
            )
            for row in rows
        )
        return MemoryRecall(query=query, hits=hits)


def _row_to_event(row: Any) -> MemoryEvent:
    """Convert an asyncpg ``Record`` to a :class:`MemoryEvent`."""
    metadata_raw = row["metadata"]
    metadata = (
        metadata_raw
        if isinstance(metadata_raw, dict)
        else json.loads(metadata_raw or "{}")
    )
    ts = row["timestamp"]
    timestamp = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
    kind: MemoryEventKind = row["kind"]
    return MemoryEvent(
        timestamp=timestamp,
        kind=kind,
        content=row["content"],
        source=row["source"],
        metadata=metadata,
    )


__all__ = ["Embedder", "PgVectorMemoryStore"]
