"""``PgAgentRuntime`` — production AgentRuntime backed by Postgres + pgvector.

Composes:
- ``agentcook_storage.PgVectorMemoryStore`` for the event-stream + recall tier
- direct asyncpg queries against the ``agents`` and ``soul_versions`` tables
  (schema owned by ``alembic/versions/0001_agents_soul_memory.py``)
- a caller-injected ``Embedder`` (Phase 2 wires
  ``agentcook_providers.OpenAIEmbedder``; Day 14 cross-package test uses a
  deterministic stub so it doesn't depend on a live OpenAI key)

This module is **the** integration point between the 4 packages — adapt
this file in Phase 2 when real-LLM embedding ships and the agent
creation path lands. Today it covers the cross-package contract
agentcook-cc reads end-to-end.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Sequence

from agentcook_core import (
    IdentityCard,
    MemoryEvent,
    MemoryRecall,
    SoulConfig,
)
from agentcook_storage import Embedder, PgVectorMemoryStore, PostgresStore

from agentcook_app.services import (
    AgentNotFoundError,
    FlushResult,
    SoulNotInitializedError,
    SoulVersion,
    StoredMemoryEvent,
)


def _now_iso() -> str:
    return dt.datetime.now(tz=dt.UTC).isoformat(timespec="seconds")


class PgAgentRuntime:
    """``AgentRuntime``-shaped adapter over Postgres + pgvector."""

    def __init__(
        self,
        store: PostgresStore,
        embedder: Embedder,
        *,
        vector_dim: int = 1536,
    ) -> None:
        self._store = store
        self._memory = PgVectorMemoryStore(store, embedder, vector_dim=vector_dim)

    async def create_agent(self, card: IdentityCard, *, user_id: str, agent_id: str | None = None) -> str:
        """Insert a new Agent row; identity is immutable from this point."""
        aid = agent_id or card.name
        await self._store.execute(
            "INSERT INTO agents (id, name, role, user_id, created_at, scopes, metadata) "
            "VALUES ($1, $2, $3, $4, $5, $6::text[], $7::jsonb)",
            aid,
            card.name,
            card.role,
            user_id,
            _parse_iso(card.created_at),
            list(card.scopes),
            json.dumps(card.metadata, ensure_ascii=False),
        )
        return aid

    async def close(self) -> None:
        await self._store.close()

    # ---- AgentRuntime protocol --------------------------------------

    async def _load_card(self, agent_id: str) -> IdentityCard:
        row = await self._store.fetchrow(
            "SELECT name, role, created_at, scopes, metadata "
            "FROM agents WHERE id = $1",
            agent_id,
        )
        if row is None:
            raise AgentNotFoundError(agent_id)
        meta = row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"] or "{}")
        created = row["created_at"]
        created_iso = created.isoformat() if hasattr(created, "isoformat") else str(created)
        return IdentityCard(
            name=row["name"],
            role=row["role"],
            created_at=created_iso,
            scopes=frozenset(row["scopes"] or ()),
            metadata=meta,
        )

    async def get_identity(self, agent_id: str) -> IdentityCard:
        return await self._load_card(agent_id)

    async def _require_agent(self, agent_id: str) -> None:
        # cheap existence check used by Soul / Memory paths so the FK isn't
        # the thing that surfaces the 404
        row = await self._store.fetchrow("SELECT 1 FROM agents WHERE id = $1", agent_id)
        if row is None:
            raise AgentNotFoundError(agent_id)

    async def get_soul_latest(self, agent_id: str) -> SoulVersion:
        await self._require_agent(agent_id)
        row = await self._store.fetchrow(
            "SELECT version, created_at, tone, language_style, values, custom_traits "
            "FROM soul_versions WHERE agent_id = $1 "
            "ORDER BY version DESC LIMIT 1",
            agent_id,
        )
        if row is None:
            raise SoulNotInitializedError(agent_id)
        return self._row_to_soul_version(row)

    async def append_soul(self, agent_id: str, config: SoulConfig) -> SoulVersion:
        await self._require_agent(agent_id)
        row = await self._store.fetchrow(
            "INSERT INTO soul_versions "
            "(agent_id, version, tone, language_style, values, custom_traits) "
            "VALUES ("
            "  $1,"
            "  COALESCE((SELECT MAX(version) FROM soul_versions WHERE agent_id = $1), 0) + 1,"
            "  $2, $3, $4::text[], $5::jsonb"
            ") "
            "RETURNING version, created_at, tone, language_style, values, custom_traits",
            agent_id,
            config.tone,
            config.language_style,
            list(config.values),
            json.dumps(config.custom_traits, ensure_ascii=False),
        )
        assert row is not None  # INSERT ... RETURNING always yields a row
        return self._row_to_soul_version(row)

    async def list_soul_history(
        self, agent_id: str, *, limit: int = 50
    ) -> Sequence[SoulVersion]:
        await self._require_agent(agent_id)
        rows = await self._store.fetch(
            "SELECT version, created_at, tone, language_style, values, custom_traits "
            "FROM soul_versions WHERE agent_id = $1 "
            "ORDER BY version ASC LIMIT $2",
            agent_id,
            limit,
        )
        return tuple(self._row_to_soul_version(r) for r in rows)

    async def append_memory_event(
        self, agent_id: str, event: MemoryEvent
    ) -> StoredMemoryEvent:
        await self._require_agent(agent_id)
        await self._memory.append_event(agent_id, event)
        # PgVectorMemoryStore.append_event doesn't RETURN ids today; fetch
        # the most recent row's id. Acceptable for v1; Day 22 can switch to
        # INSERT ... RETURNING id once we stop calling append_event directly.
        row = await self._store.fetchrow(
            "SELECT id FROM memory_events WHERE agent_id = $1 "
            "ORDER BY id DESC LIMIT 1",
            agent_id,
        )
        return StoredMemoryEvent(id=f"evt_{row['id']}", event=event)

    async def list_memory_events(
        self,
        agent_id: str,
        *,
        since: str | None = None,
        kind: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[Sequence[StoredMemoryEvent], str | None]:
        await self._require_agent(agent_id)
        # cursor is "evt_<int>"; pagination is "id > cursor_int"
        clauses = ["agent_id = $1"]
        args: list[object] = [agent_id]
        if since is not None:
            args.append(_parse_iso(since))
            clauses.append(f"timestamp >= ${len(args)}")
        if kind is not None:
            args.append(kind)
            clauses.append(f"kind = ${len(args)}")
        if cursor is not None:
            try:
                cursor_int = int(cursor.removeprefix("evt_"))
            except ValueError as exc:
                raise AgentNotFoundError(agent_id) from exc  # treat malformed cursor as not-found
            args.append(cursor_int)
            clauses.append(f"id > ${len(args)}")
        args.append(limit + 1)  # fetch one extra to know if there's a next page
        query = (
            "SELECT id, timestamp, kind, content, source, metadata "
            "FROM memory_events "
            f"WHERE {' AND '.join(clauses)} "
            f"ORDER BY id ASC LIMIT ${len(args)}"
        )
        rows = list(await self._store.fetch(query, *args))
        has_more = len(rows) > limit
        page = rows[:limit]
        stored = tuple(
            StoredMemoryEvent(
                id=f"evt_{r['id']}",
                event=MemoryEvent(
                    timestamp=r["timestamp"].isoformat(),
                    kind=r["kind"],
                    content=r["content"],
                    source=r["source"],
                    metadata=(
                        r["metadata"] if isinstance(r["metadata"], dict)
                        else json.loads(r["metadata"] or "{}")
                    ),
                ),
            )
            for r in page
        )
        next_cursor = stored[-1].id if has_more and stored else None
        return stored, next_cursor

    async def search_memory(
        self, agent_id: str, query: str, *, top_k: int = 5
    ) -> MemoryRecall:
        await self._require_agent(agent_id)
        return await self._memory.search(agent_id, query, top_k=top_k)

    async def flush_memory(
        self, agent_id: str, *, preserve_identity_and_soul: bool = True
    ) -> FlushResult:
        await self._require_agent(agent_id)
        deleted_row = await self._store.fetchrow(
            "WITH deleted AS ("
            "  DELETE FROM memory_events WHERE agent_id = $1 RETURNING 1"
            ") SELECT count(*) AS n FROM deleted",
            agent_id,
        )
        count = int(deleted_row["n"]) if deleted_row else 0
        soul_preserved = preserve_identity_and_soul
        if not preserve_identity_and_soul:
            await self._store.execute(
                "DELETE FROM soul_versions WHERE agent_id = $1", agent_id
            )
        return FlushResult(
            deleted_event_count=count,
            identity_preserved=True,
            soul_preserved=soul_preserved,
        )

    # ---- helpers ----------------------------------------------------

    def _row_to_soul_version(self, row) -> SoulVersion:
        traits_raw = row["custom_traits"]
        traits = (
            traits_raw if isinstance(traits_raw, dict)
            else json.loads(traits_raw or "{}")
        )
        return SoulVersion(
            version=int(row["version"]),
            created_at=row["created_at"].isoformat(),
            config=SoulConfig(
                tone=row["tone"],
                language_style=row["language_style"],
                values=tuple(row["values"] or ()),
                custom_traits=traits,
            ),
        )


def _parse_iso(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value)


__all__ = ["PgAgentRuntime"]
