"""Contract tests for storage protocols.

Pure-Python in-memory fakes verify the protocol shape. Real PG / Redis /
S3 round-trips live in ``test_integration.py`` (marker ``integration``,
spun up via testcontainers — opt in with ``pytest -m integration``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

pytestmark = pytest.mark.unit

from agentcook_core import (  # noqa: E402
    MemoryEvent,
    MemoryStoreProtocol,
)
from agentcook_storage import (  # noqa: E402
    KeyValueStoreProtocol,
    ObjectStoreProtocol,
    PgVectorMemoryStore,
    PostgresStore,
    RedisStore,
    S3ObjectStore,
    SqlStoreProtocol,
)
from agentcook_storage.memory_store import _format_vector  # noqa: E402


# --------------------------- SqlStore ---------------------------

class _FakeSqlStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []

    async def execute(self, query: str, *args: Any) -> str:
        self.calls.append(("execute", query, args))
        return "OK"

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        self.calls.append(("fetch", query, args))
        return [{"id": 1}]

    async def fetchrow(self, query: str, *args: Any) -> Any | None:
        self.calls.append(("fetchrow", query, args))
        return {"id": 1}

    async def close(self) -> None:
        self.calls.append(("close", "", ()))


def test_fake_sql_store_satisfies_protocol() -> None:
    assert isinstance(_FakeSqlStore(), SqlStoreProtocol)


async def test_fake_sql_store_round_trip() -> None:
    store = _FakeSqlStore()
    assert await store.execute("INSERT INTO t VALUES ($1)", 1) == "OK"
    rows = await store.fetch("SELECT * FROM t")
    assert rows == [{"id": 1}]
    assert (await store.fetchrow("SELECT 1"))["id"] == 1
    await store.close()


def test_real_postgres_store_class_satisfies_protocol_signature() -> None:
    """PostgresStore exposes the SqlStoreProtocol shape even without a pool."""
    # We don't instantiate (would require a live PG). The class itself
    # provides all required attributes — Protocol checks structural typing
    # against an instance, but the method shape is what we verify here.
    for attr in ("execute", "fetch", "fetchrow", "close"):
        assert hasattr(PostgresStore, attr)


# --------------------------- KeyValueStore ---------------------------

class _FakeKVStore:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._data.get(key)

    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None:
        self._data[key] = value  # TTL ignored in the fake

    async def delete(self, key: str) -> int:
        return 1 if self._data.pop(key, None) is not None else 0

    async def close(self) -> None:
        self._data.clear()


def test_fake_kv_store_satisfies_protocol() -> None:
    assert isinstance(_FakeKVStore(), KeyValueStoreProtocol)


async def test_fake_kv_store_round_trip() -> None:
    store = _FakeKVStore()
    assert await store.get("missing") is None
    await store.set("k", "v", ttl_seconds=60)
    assert await store.get("k") == "v"
    assert await store.delete("k") == 1
    assert await store.delete("k") == 0
    await store.close()


def test_real_redis_store_class_signature() -> None:
    for attr in ("get", "set", "delete", "close"):
        assert hasattr(RedisStore, attr)


# --------------------------- ObjectStore ---------------------------

class _FakeObjectStore:
    def __init__(self) -> None:
        self._data: dict[tuple[str, str], bytes] = {}

    async def put_object(self, bucket: str, key: str, body: bytes) -> None:
        self._data[(bucket, key)] = body

    async def get_object(self, bucket: str, key: str) -> bytes:
        return self._data[(bucket, key)]

    async def delete_object(self, bucket: str, key: str) -> None:
        self._data.pop((bucket, key), None)

    async def list_objects(self, bucket: str, prefix: str = "") -> AsyncIterator[str]:
        for b, k in self._data:
            if b == bucket and k.startswith(prefix):
                yield k

    async def presigned_url(self, bucket: str, key: str, *, expires_in: int = 3600) -> str:
        return f"https://example.com/{bucket}/{key}?exp={expires_in}"


def test_fake_object_store_satisfies_protocol() -> None:
    assert isinstance(_FakeObjectStore(), ObjectStoreProtocol)


async def test_fake_object_store_round_trip() -> None:
    store = _FakeObjectStore()
    await store.put_object("b", "k1", b"hello")
    await store.put_object("b", "k2", b"world")
    assert await store.get_object("b", "k1") == b"hello"
    keys = [k async for k in store.list_objects("b", prefix="k")]
    assert set(keys) == {"k1", "k2"}
    url = await store.presigned_url("b", "k1", expires_in=60)
    assert "exp=60" in url
    await store.delete_object("b", "k1")
    keys_after = [k async for k in store.list_objects("b")]
    assert keys_after == ["k2"]


def test_real_s3_object_store_class_signature() -> None:
    for attr in ("put_object", "get_object", "delete_object", "list_objects", "presigned_url"):
        assert hasattr(S3ObjectStore, attr)


# --------------------------- PgVectorMemoryStore (unit, mock-PG) ---------------------------

class _RecordingPgStore:
    """Tiny in-memory stand-in for PostgresStore — records every call."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self.fetched: list[tuple[str, tuple[Any, ...]]] = []
        self.fetch_result: list[dict[str, Any]] = []

    async def execute(self, query: str, *args: Any) -> str:
        self.executed.append((query, args))
        return "OK"

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.fetched.append((query, args))
        return list(self.fetch_result)

    async def fetchrow(self, query: str, *args: Any) -> Any | None:
        return None

    async def close(self) -> None:
        pass


async def _stub_embed(text: str) -> list[float]:
    """Deterministic fake embedder for unit tests (no network)."""
    return [float(len(text)) / 10, 0.1, 0.2]


def test_pgvector_memory_store_satisfies_memory_store_protocol() -> None:
    store = PgVectorMemoryStore(_RecordingPgStore(), _stub_embed, vector_dim=3)  # type: ignore[arg-type]
    assert isinstance(store, MemoryStoreProtocol)


async def test_pgvector_memory_store_ensure_schema_issues_create_statements() -> None:
    pg = _RecordingPgStore()
    store = PgVectorMemoryStore(pg, _stub_embed, vector_dim=3)  # type: ignore[arg-type]
    await store.ensure_schema()
    assert any("CREATE TABLE IF NOT EXISTS memory_events" in q for q, _ in pg.executed)
    assert any("VECTOR(3)" in q for q, _ in pg.executed)
    assert any("memory_events_agent_ts_idx" in q for q, _ in pg.executed)


async def test_pgvector_memory_store_append_event_inserts_with_embedding() -> None:
    pg = _RecordingPgStore()
    store = PgVectorMemoryStore(pg, _stub_embed, vector_dim=3)  # type: ignore[arg-type]
    event = MemoryEvent(
        timestamp="2026-05-19T10:00:00Z",
        kind="observation",
        content="user likes pgvector",
        source="chat-1",
        metadata={"intent": "preference"},
    )
    await store.append_event("agent-A", event)

    assert len(pg.executed) == 1
    query, args = pg.executed[0]
    assert "INSERT INTO memory_events" in query
    assert "::vector" in query and "::jsonb" in query
    # args: (agent_id, timestamp_dt, kind, content, source, metadata_json, vector_str)
    assert args[0] == "agent-A"
    # timestamp is parsed to datetime before binding (asyncpg requires it)
    from datetime import datetime
    assert isinstance(args[1], datetime)
    assert args[2] == "observation"
    assert '"intent"' in args[5]  # metadata serialized as JSON
    assert args[6].startswith("[") and args[6].endswith("]")  # vector literal


async def test_pgvector_memory_store_search_uses_cosine_distance_operator() -> None:
    pg = _RecordingPgStore()
    pg.fetch_result = [
        {
            "timestamp": "2026-05-19T10:00:00Z",
            "kind": "observation",
            "content": "user likes pgvector",
            "source": "chat-1",
            "metadata": {},
            "score": 0.93,
        }
    ]
    store = PgVectorMemoryStore(pg, _stub_embed, vector_dim=3)  # type: ignore[arg-type]
    recall = await store.search("agent-A", "pgvector", top_k=3)

    assert recall.query == "pgvector" and len(recall.hits) == 1
    hit = recall.hits[0]
    assert hit.score == 0.93 and "pgvector" in hit.content
    assert hit.event is not None and hit.event.kind == "observation"

    query, args = pg.fetched[0]
    # cosine distance operator + injected top_k
    assert "embedding <=> $2::vector" in query
    assert args[0] == "agent-A" and args[2] == 3


async def test_pgvector_memory_store_session_kv_raises_not_implemented() -> None:
    store = PgVectorMemoryStore(_RecordingPgStore(), _stub_embed, vector_dim=3)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError, match="RedisStore"):
        await store.remember_session("s", "k", "v")
    with pytest.raises(NotImplementedError, match="RedisStore"):
        await store.recall_session("s", "k")


def test_format_vector_produces_pgvector_literal() -> None:
    assert _format_vector([0.1, 0.2, 0.3]).startswith("[0.1,0.2,0.3")
    assert _format_vector([]) == "[]"
