"""Postgres-backed runtime, end to end (testcontainers + pgvector).

Each test module gets a fresh database inside the shared container, so
alembic runs from zero and other integration suites are unaffected.
"""

from __future__ import annotations

import asyncio
import dataclasses
import uuid
from collections.abc import Iterator

import pytest
from agentcook_core import Message, ToolCall
from agentcook_core.conversations import SessionAccessError
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def database_url(pg_container) -> Iterator[str]:  # type: ignore[no-untyped-def]
    import psycopg

    admin_dsn = pg_container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
    name = f"agentcook_it_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    base, _, _ = admin_dsn.rpartition("/")
    yield f"{base}/{name}"


@pytest.fixture(scope="module")
def migrated(database_url: str) -> str:
    from agentcook_app.db import run_migrations

    run_migrations(database_url)
    run_migrations(database_url)  # idempotent
    return database_url


async def _store(dsn: str):  # type: ignore[no-untyped-def]
    from agentcook_storage import PgConversationStore, PostgresStore

    pg = await PostgresStore.connect(dsn)
    return pg, PgConversationStore(pg)


async def test_migrations_create_all_tables(migrated: str) -> None:
    from agentcook_storage import PostgresStore

    pg = await PostgresStore.connect(migrated)
    try:
        rows = await pg.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        tables = {r["table_name"] for r in rows}
        version = await pg.fetchrow("SELECT version_num FROM alembic_version")
    finally:
        await pg.close()
    assert {
        "agents",
        "soul_versions",
        "memory_events",
        "conversations",
        "conversation_messages",
    } <= tables
    assert version["version_num"] == "0002_conversations"


async def test_conversation_store_round_trip(migrated: str) -> None:
    pg, store = await _store(migrated)
    try:
        summary = await store.ensure_session(
            "s-1", user_id="alice", agent="assistant", title="Hello there"
        )
        assert summary.title == "Hello there" and summary.message_count == 0
        again = await store.ensure_session("s-1", user_id="alice", agent="assistant")
        assert again.created_at == summary.created_at
        with pytest.raises(SessionAccessError):
            await store.ensure_session("s-1", user_id="bob", agent="assistant")

        call = ToolCall(id="c1", name="calculator", arguments={"expression": "1+1", "中": "文"})
        await store.append_messages(
            "s-1",
            [
                Message(role="user", content="1+1?"),
                Message(role="assistant", content="", tool_calls=(call,)),
                Message(role="tool", content="2", name="calculator", tool_call_id="c1"),
                Message(
                    role="assistant",
                    content="2",
                    metadata={"run_id": "r1", "usage": {"input_tokens": 3}},
                ),
            ],
        )
        loaded = await store.load_messages("s-1", user_id="alice")
        assert [m.role for m in loaded] == ["user", "assistant", "tool", "assistant"]
        assert loaded[1].tool_calls == (call,)
        assert loaded[2].tool_call_id == "c1" and loaded[2].name == "calculator"
        assert loaded[3].metadata["usage"] == {"input_tokens": 3}
        assert "created_at" in loaded[0].metadata
        assert [m.content for m in await store.load_messages("s-1", user_id="alice", limit=2)] == [
            "2",
            "2",
        ]
        assert await store.load_messages("s-1", user_id="bob") == []
        assert await store.get_session("s-1", user_id="bob") is None

        await store.ensure_session("s-2", user_id="alice", agent="analyst", title="Second")
        listing = await store.list_sessions("alice")
        assert [s.session_id for s in listing] == ["s-2", "s-1"]
        assert listing[1].message_count == 4

        renamed = await store.rename_session("s-1", user_id="alice", title="Math")
        assert renamed is not None and renamed.title == "Math"
        assert await store.rename_session("s-1", user_id="bob", title="x") is None
        assert not await store.delete_session("s-1", user_id="bob")
        assert await store.delete_session("s-1", user_id="alice")
        assert await store.load_messages("s-1", user_id="alice") == []
    finally:
        await pg.close()


async def test_concurrent_appends_keep_order_and_count(migrated: str) -> None:
    pg, store = await _store(migrated)
    try:
        await store.ensure_session("busy", user_id="u", agent="assistant")
        await asyncio.gather(
            *(
                store.append_messages(
                    "busy",
                    [
                        Message(role="user", content=f"{i}-a"),
                        Message(role="assistant", content=f"{i}-b"),
                    ],
                )
                for i in range(10)
            )
        )
        loaded = await store.load_messages("busy", user_id="u")
        assert len(loaded) == 20
        # each append's pair stays contiguous
        for first, second in zip(loaded[::2], loaded[1::2], strict=True):
            assert first.content.split("-")[0] == second.content.split("-")[0]
        summary = await store.get_session("busy", user_id="u")
        assert summary is not None and summary.message_count == 20
    finally:
        await pg.close()


def test_app_on_postgres_survives_restart(migrated: str) -> None:
    from agentcook_app.config import Settings
    from agentcook_app.main import create_app

    settings = dataclasses.replace(
        Settings.from_env({}), storage="postgres", database_url=migrated, db_auto_migrate=True
    )

    with TestClient(create_app(settings)) as client:
        r = client.post(
            "/api/v1/chat/stream", json={"session_id": "pg-1", "message": "calculate 6 * 7"}
        )
        assert r.status_code == 200 and '"type": "done"' in r.text
        r = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "pg-2", "message": "remember that I sell earbuds in Europe"},
        )
        assert '"name": "remember"' in r.text
        ready = client.get("/health/ready").json()
        assert ready["checks"]["postgres"]["status"] == "up"

    # A fresh process sees the same transcript + memory.
    with TestClient(create_app(settings)) as client:
        transcript = client.get("/api/v1/conversations/pg-1").json()
        assert transcript["messages"][1]["tool_calls"][0]["name"] == "calculator"
        assert "42" in transcript["messages"][1]["tool_calls"][0]["output"]
        r = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "pg-3", "message": "do you remember where I sell earbuds"},
        )
        assert "earbuds in Europe" in r.text
        assert {c["id"] for c in client.get("/api/v1/conversations").json()["items"]} == {
            "pg-1",
            "pg-2",
            "pg-3",
        }
