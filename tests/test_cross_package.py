"""Cross-package integration tests — 4-pkg matrix in one place.

Documents the contract between the four Python packages of agentcook-cc:

- ``agentcook-core``       (protocols + value types, zero runtime deps)
- ``agentcook-providers``  (LLM transport adapters)
- ``agentcook-storage``    (PG/Redis/S3 + PgVectorMemoryStore)
- ``agentcook``            (FastAPI runtime composed from the above)

Three of the four edges are tested as ``unit`` (pure-Python structural
checks); the ``core × agentcook`` edge is ``integration`` because it
spins a real pgvector container and round-trips events through HTTP.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import time
from collections.abc import Awaitable, Callable, Iterator
from typing import Any

import jwt
import pytest

# --------------------------------------------------------------------------
# Unit-marker cross-package contract checks
# --------------------------------------------------------------------------


@pytest.mark.unit
def test_core_x_providers_openai_satisfies_llm_provider_protocol() -> None:
    """`agentcook-providers` exports types that satisfy core's protocol."""
    from agentcook_core import LLMProviderProtocol
    from agentcook_providers import EchoProvider, OpenAIProvider

    # EchoProvider is concrete (no client needed)
    assert isinstance(EchoProvider(), LLMProviderProtocol)

    # OpenAIProvider can't be instantiated without an SDK client,
    # but the class itself MUST expose every protocol attribute.
    for attr in ("model_name", "context_window", "chat", "stream_chat", "count_tokens"):
        assert hasattr(OpenAIProvider, attr), f"OpenAIProvider missing {attr}"


@pytest.mark.unit
def test_core_x_storage_pgvector_satisfies_memory_store_protocol() -> None:
    """`agentcook-storage` exports a MemoryStoreProtocol-shaped impl."""
    from agentcook_core import MemoryStoreProtocol
    from agentcook_storage import PgVectorMemoryStore

    # Smoke-construct with stubs (no live PG required for structural check).
    class _StubPg:
        async def execute(self, *a, **k): return "OK"
        async def fetch(self, *a, **k): return []
        async def fetchrow(self, *a, **k): return None
        async def close(self): pass

    async def stub_embed(text: str) -> list[float]:
        return [0.0, 0.0, 0.0]

    store = PgVectorMemoryStore(_StubPg(), stub_embed, vector_dim=3)  # type: ignore[arg-type]
    assert isinstance(store, MemoryStoreProtocol)


@pytest.mark.unit
def test_providers_x_storage_embedder_wiring_shape() -> None:
    """``PgVectorMemoryStore`` accepts any embedder of the documented shape.

    The Phase 2 wiring will replace this stub with
    ``agentcook_providers.OpenAIProvider``-derived ``OpenAIEmbedder``;
    Day 14 just proves the type contract holds across the boundary.
    """
    from agentcook_storage import Embedder, PgVectorMemoryStore

    # Any async callable returning a sequence of floats satisfies Embedder.
    async def dim3_embedder(text: str) -> list[float]:
        return [float(len(text)) % 1.0, 0.5, 0.25]

    # Static check: type matches the Embedder alias.
    e: Embedder = dim3_embedder

    class _StubPg:
        async def execute(self, *a, **k): return "OK"
        async def fetch(self, *a, **k): return []
        async def fetchrow(self, *a, **k): return None
        async def close(self): pass

    store = PgVectorMemoryStore(_StubPg(), e, vector_dim=3)  # type: ignore[arg-type]
    assert callable(e)
    assert store is not None


@pytest.mark.unit
def test_core_x_agentcook_pg_runtime_satisfies_agent_runtime_protocol() -> None:
    """The Phase 2 PgAgentRuntime adapter exposes the AgentRuntime contract."""
    from agentcook_app.runtime_pg import PgAgentRuntime

    # Structural check via attribute presence (PgAgentRuntime constructor
    # needs a live store; we only assert the class shape here).
    runtime_methods = {
        "get_identity", "get_soul_latest", "append_soul", "list_soul_history",
        "append_memory_event", "list_memory_events", "search_memory", "flush_memory",
    }
    assert runtime_methods <= set(dir(PgAgentRuntime))


# --------------------------------------------------------------------------
# Integration: core × storage × agentcook end-to-end via real pgvector + HTTP
# --------------------------------------------------------------------------


def _docker_available() -> bool:
    try:
        import docker
        docker.from_env(timeout=2).ping()
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def _pgvector_dsn() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker daemon not reachable")
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer("pgvector/pgvector:pg16")
    container.start()
    try:
        # asyncpg needs the server to be past startup recovery; poll until ready.
        host = container.get_container_host_ip()
        port = int(container.get_exposed_port(5432))
        dsn = container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")

        async def _ping() -> None:
            import asyncpg
            deadline = time.time() + 60
            while time.time() < deadline:
                try:
                    conn = await asyncpg.connect(dsn)
                    await conn.execute("SELECT 1")
                    await conn.close()
                    return
                except Exception:
                    await asyncio.sleep(0.5)
            raise RuntimeError(f"pgvector container not accepting connections at {dsn}")

        asyncio.new_event_loop().run_until_complete(_ping())
        _ = host, port  # consumed for readiness check
        yield dsn
    finally:
        container.stop()


def _make_token() -> str:
    os.environ.setdefault("AGENTCOOK_JWT_SECRET", "test-secret-do-not-use-anywhere-else")
    return jwt.encode(
        {
            "sub": "user-1",
            "scopes": "agent:read agent:write",
            "exp": dt.datetime.now(tz=dt.UTC) + dt.timedelta(minutes=15),
        },
        os.environ["AGENTCOOK_JWT_SECRET"],
        algorithm="HS256",
    )


@pytest.mark.integration
async def test_core_x_agentcook_end_to_end_via_http_and_pgvector(_pgvector_dsn: str) -> None:
    """POST event → search → flush via FastAPI, backed by real pgvector.

    This is the canonical "all four packages talking" test:
    - agentcook (FastAPI runtime) hosts the routers
    - agentcook-storage's PostgresStore + PgVectorMemoryStore stores events
    - agentcook-core's MemoryStoreProtocol mediates the contract
    - agentcook-providers' Embedder type alias shapes the injection point
      (deterministic stub embedder; Phase 2 swaps to OpenAIEmbedder)

    The test is ``async`` so the asyncpg pool stays bound to a single
    event loop across setup → HTTP calls → teardown. (TestClient creates
    its own thread/loop, which trips ``InterfaceError: another operation
    is in progress`` when the pool was opened on the test loop.)
    """
    import httpx
    from agentcook_app.main import create_app
    from agentcook_app.runtime_pg import PgAgentRuntime
    from agentcook_app.services import get_runtime
    from agentcook_core import IdentityCard
    from agentcook_storage import PostgresStore, ensure_pgvector_extension

    async def stub_embed(text: str) -> list[float]:
        # Deterministic 3-D embedder: pgvector word → [1,0,0]; redis → [0,1,0].
        mapping: dict[str, list[float]] = {
            "pgvector is fast": [1.0, 0.0, 0.0],
            "redis is fast": [0.0, 1.0, 0.0],
            "search query about pgvector": [0.95, 0.05, 0.0],
        }
        return mapping.get(text, [0.0, 0.0, 1.0])

    store = await PostgresStore.connect(_pgvector_dsn)
    try:
        await ensure_pgvector_extension(store)

        # NF-3 (Day 17): use alembic as single source of truth for DDL.
        # Run `alembic upgrade head` against the ephemeral test DB instead
        # of the now-deleted PgAgentRuntime.ensure_schema().
        import subprocess
        alembic_dir = os.path.join(os.path.dirname(__file__), "..", "agentcook")
        psycopg_dsn = _pgvector_dsn.replace("postgresql://", "postgresql+psycopg://")
        subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            cwd=alembic_dir,
            env={**os.environ, "AGENTCOOK_DB_URL": psycopg_dsn},
            check=True,
            capture_output=True,
            timeout=30,
        )
        # Alembic migration creates VECTOR(1536); tests use a 3-dim stub
        # embedder.  Resize the column for the ephemeral test DB only.
        await store.execute(
            "ALTER TABLE memory_events "
            "ALTER COLUMN embedding TYPE vector(3) USING embedding::vector(3)"
        )

        runtime = PgAgentRuntime(store, stub_embed, vector_dim=3)
        await runtime.create_agent(
            IdentityCard(
                name="agent-int",
                role="assistant",
                created_at="2026-05-22T00:00:00+00:00",
                scopes=frozenset({"chat", "search"}),
            ),
            user_id="user-1",
            agent_id="agent-int",
        )

        app = create_app()
        app.dependency_overrides[get_runtime] = lambda: runtime
        transport = httpx.ASGITransport(app=app)
        headers = {"Authorization": f"Bearer {_make_token()}"}

        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Identity round-trip
            r = await client.get("/api/v1/agents/agent-int/identity", headers=headers)
            assert r.status_code == 200, r.text
            assert r.json()["name"] == "agent-int"

            # 2. Append two events with different embeddings
            for content in ("pgvector is fast", "redis is fast"):
                r = await client.post(
                    "/api/v1/agents/agent-int/memory/events",
                    headers=headers,
                    json={"kind": "observation", "content": content},
                )
                assert r.status_code == 201, r.text

            # 3. Search must rank the pgvector-similar event first
            r = await client.post(
                "/api/v1/agents/agent-int/memory/search",
                headers=headers,
                json={"query": "search query about pgvector", "top_k": 2},
            )
            assert r.status_code == 200, r.text
            hits = r.json()["hits"]
            assert len(hits) == 2
            assert "pgvector" in hits[0]["content"]
            assert hits[0]["score"] > hits[1]["score"]

            # 4. List events shows both insertions in order
            r = await client.get("/api/v1/agents/agent-int/memory/events", headers=headers)
            assert r.status_code == 200
            assert len(r.json()["items"]) == 2

            # 5. Flush wipes events but preserves identity
            r = await client.post(
                "/api/v1/agents/agent-int/memory/flush",
                headers=headers,
                json={
                    "confirm": "I understand this deletes all events for this agent.",
                    "preserve_identity_and_soul": True,
                },
            )
            assert r.status_code == 200
            assert r.json()["deleted_event_count"] == 2
            assert r.json()["identity_preserved"] is True

            # 6. Identity survived the flush
            r = await client.get("/api/v1/agents/agent-int/identity", headers=headers)
            assert r.status_code == 200 and r.json()["name"] == "agent-int"
    finally:
        await store.execute("DROP TABLE IF EXISTS memory_events CASCADE")
        await store.execute("DROP TABLE IF EXISTS soul_versions CASCADE")
        await store.execute("DROP TABLE IF EXISTS agents CASCADE")
        await store.close()


# Keep linter happy about the indirect import.
_ = Any
_ = Callable
_ = Awaitable
