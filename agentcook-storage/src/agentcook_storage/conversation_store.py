"""PostgreSQL :class:`ConversationStoreProtocol` implementation.

Schema is owned by alembic (``agentcook/alembic/versions/0002_conversations.py``);
:meth:`PgConversationStore.ensure_schema` exists for tests and
single-binary dev setups only.

Appends are serialized per conversation with ``SELECT … FOR UPDATE`` so
concurrent requests on the same session can never interleave sequence
numbers.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Sequence
from typing import Any

from agentcook_core import Message, ToolCall
from agentcook_core.conversations import (
    ConversationSummary,
    SessionAccessError,
    derive_title,
)

from agentcook_storage.postgres import PostgresStore

CONVERSATIONS_DDL = (
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id            TEXT PRIMARY KEY,
        user_id       TEXT NOT NULL,
        agent         TEXT NOT NULL,
        title         TEXT NOT NULL,
        metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
        message_count INTEGER NOT NULL DEFAULT 0,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS conversations_user_updated_idx
        ON conversations (user_id, updated_at DESC)
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_messages (
        id              BIGSERIAL PRIMARY KEY,
        conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        seq             INTEGER NOT NULL,
        role            TEXT NOT NULL,
        content         TEXT NOT NULL,
        name            TEXT,
        tool_call_id    TEXT,
        tool_calls      JSONB,
        metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (conversation_id, seq)
    )
    """,
)

_SUMMARY_COLUMNS = "id, user_id, agent, title, metadata, message_count, created_at, updated_at"


def _iso(value: Any) -> str:
    if isinstance(value, dt.datetime):
        return value.isoformat(timespec="milliseconds")
    return str(value)


def _json(value: Any) -> Any:
    if value is None or isinstance(value, (dict, list)):
        return value
    return json.loads(value)


def _row_to_summary(row: Any) -> ConversationSummary:
    return ConversationSummary(
        session_id=row["id"],
        user_id=row["user_id"],
        agent=row["agent"],
        title=row["title"],
        created_at=_iso(row["created_at"]),
        updated_at=_iso(row["updated_at"]),
        message_count=row["message_count"],
        metadata=_json(row["metadata"]) or {},
    )


def _row_to_message(row: Any) -> Message:
    raw_calls = _json(row["tool_calls"])
    calls = (
        tuple(
            ToolCall(id=c["id"], name=c["name"], arguments=c.get("arguments") or {})
            for c in raw_calls
        )
        if raw_calls
        else None
    )
    metadata = _json(row["metadata"]) or {}
    metadata.setdefault("created_at", _iso(row["created_at"]))
    return Message(
        role=row["role"],
        content=row["content"],
        name=row["name"],
        tool_call_id=row["tool_call_id"],
        tool_calls=calls,
        metadata=metadata,
    )


class PgConversationStore:
    """Transcript persistence over :class:`PostgresStore`."""

    def __init__(self, store: PostgresStore) -> None:
        self._store = store

    async def ensure_schema(self) -> None:
        for statement in CONVERSATIONS_DDL:
            await self._store.execute(statement)

    async def ensure_session(
        self,
        session_id: str,
        *,
        user_id: str,
        agent: str,
        title: str | None = None,
    ) -> ConversationSummary:
        row = await self._store.fetchrow(
            f"INSERT INTO conversations (id, user_id, agent, title) VALUES ($1, $2, $3, $4) "
            f"ON CONFLICT (id) DO NOTHING RETURNING {_SUMMARY_COLUMNS}",
            session_id,
            user_id,
            agent,
            derive_title(title or ""),
        )
        if row is None:
            row = await self._store.fetchrow(
                f"SELECT {_SUMMARY_COLUMNS} FROM conversations WHERE id = $1", session_id
            )
            assert row is not None
        summary = _row_to_summary(row)
        if summary.user_id != user_id:
            raise SessionAccessError(session_id)
        return summary

    async def get_session(self, session_id: str, *, user_id: str) -> ConversationSummary | None:
        row = await self._store.fetchrow(
            f"SELECT {_SUMMARY_COLUMNS} FROM conversations WHERE id = $1 AND user_id = $2",
            session_id,
            user_id,
        )
        return _row_to_summary(row) if row is not None else None

    async def append_messages(self, session_id: str, messages: Sequence[Message]) -> None:
        if not messages:
            return
        async with self._store.transaction() as conn:
            count = await conn.fetchval(
                "SELECT message_count FROM conversations WHERE id = $1 FOR UPDATE", session_id
            )
            if count is None:
                raise KeyError(f"session {session_id!r} does not exist")
            rows = []
            for offset, msg in enumerate(messages):
                calls = (
                    json.dumps(
                        [
                            {"id": c.id, "name": c.name, "arguments": c.arguments}
                            for c in msg.tool_calls
                        ],
                        ensure_ascii=False,
                    )
                    if msg.tool_calls
                    else None
                )
                meta = {k: v for k, v in msg.metadata.items() if k != "created_at"}
                rows.append(
                    (
                        session_id,
                        count + offset + 1,
                        msg.role,
                        msg.content,
                        msg.name,
                        msg.tool_call_id,
                        calls,
                        json.dumps(meta, ensure_ascii=False, default=str),
                    )
                )
            await conn.executemany(
                "INSERT INTO conversation_messages "
                "(conversation_id, seq, role, content, name, tool_call_id, tool_calls, metadata) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb)",
                rows,
            )
            await conn.execute(
                "UPDATE conversations SET message_count = $2, updated_at = now() WHERE id = $1",
                session_id,
                count + len(messages),
            )

    async def load_messages(
        self, session_id: str, *, user_id: str, limit: int | None = None
    ) -> list[Message]:
        owner = await self._store.fetchrow(
            "SELECT 1 FROM conversations WHERE id = $1 AND user_id = $2", session_id, user_id
        )
        if owner is None:
            return []
        if limit:
            rows = await self._store.fetch(
                "SELECT * FROM (SELECT seq, role, content, name, tool_call_id, tool_calls, "
                "metadata, created_at FROM conversation_messages WHERE conversation_id = $1 "
                "ORDER BY seq DESC LIMIT $2) recent ORDER BY seq ASC",
                session_id,
                limit,
            )
        else:
            rows = await self._store.fetch(
                "SELECT seq, role, content, name, tool_call_id, tool_calls, metadata, created_at "
                "FROM conversation_messages WHERE conversation_id = $1 ORDER BY seq ASC",
                session_id,
            )
        return [_row_to_message(r) for r in rows]

    async def list_sessions(self, user_id: str, *, limit: int = 50) -> list[ConversationSummary]:
        rows = await self._store.fetch(
            f"SELECT {_SUMMARY_COLUMNS} FROM conversations WHERE user_id = $1 "
            "ORDER BY updated_at DESC LIMIT $2",
            user_id,
            limit,
        )
        return [_row_to_summary(r) for r in rows]

    async def rename_session(
        self, session_id: str, *, user_id: str, title: str
    ) -> ConversationSummary | None:
        row = await self._store.fetchrow(
            f"UPDATE conversations SET title = $3, updated_at = now() "
            f"WHERE id = $1 AND user_id = $2 RETURNING {_SUMMARY_COLUMNS}",
            session_id,
            user_id,
            derive_title(title),
        )
        return _row_to_summary(row) if row is not None else None

    async def delete_session(self, session_id: str, *, user_id: str) -> bool:
        status = await self._store.execute(
            "DELETE FROM conversations WHERE id = $1 AND user_id = $2", session_id, user_id
        )
        return status.endswith(" 1")


__all__ = ["CONVERSATIONS_DDL", "PgConversationStore"]
