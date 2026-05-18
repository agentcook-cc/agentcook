"""Real-container integration tests for storage backends.

Marker: ``integration`` — opt in with ``pytest -m integration``. Requires
a running Docker daemon; skips gracefully when unavailable.

- :class:`RedisStore` against the monorepo-wide ``redis_container``
  fixture (Agent C's ``conftest.py`` at the repo root).
- :class:`S3ObjectStore` against a MinIO container spun up here (no
  ``testcontainers.minio`` dependency — uses the generic
  ``DockerContainer`` so we don't need to install the ``minio`` SDK).
- :class:`PostgresStore` + :class:`PgVectorMemoryStore` against a
  pgvector-enabled Postgres container spun up here (independent of
  Agent C's ``pg_container`` which currently uses a plain image).
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

pytestmark = pytest.mark.integration


def _docker_available() -> bool:
    try:
        import docker

        docker.from_env(timeout=2).ping()
        return True
    except Exception:
        return False


# --------------------------- RedisStore --------------------------------------

async def test_redis_store_round_trip(redis_container) -> None:
    """RedisStore set/get/delete + TTL against a real Redis container."""
    from agentcook_storage import RedisStore

    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    store = RedisStore.from_url(f"redis://{host}:{port}/0")
    try:
        assert await store.get("absent") is None
        await store.set("k1", "v1")
        assert await store.get("k1") == "v1"
        await store.set("k2", "v2", ttl_seconds=60)
        assert await store.get("k2") == "v2"
        assert await store.delete("k1") == 1
        assert await store.delete("k1") == 0
    finally:
        await store.close()


# --------------------------- S3ObjectStore (MinIO) --------------------------

@pytest.fixture(scope="module")
def minio_container() -> Iterator[object]:
    """MinIO container exposing the S3 API on a random port."""
    if not _docker_available():
        pytest.skip("Docker daemon not reachable; skipping S3 integration tests")
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.waiting_utils import wait_for_logs

    container = (
        DockerContainer("minio/minio:latest")
        .with_command("server /data")
        .with_env("MINIO_ROOT_USER", "minioadmin")
        .with_env("MINIO_ROOT_PASSWORD", "minioadmin")
        .with_exposed_ports(9000)
    )
    container.start()
    try:
        wait_for_logs(container, "API:", timeout=30)
        # Poll the readiness endpoint as well — wait_for_logs alone catches
        # the server startup line but MinIO may still 503 briefly.
        host = container.get_container_host_ip()
        port = container.get_exposed_port(9000)
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                urllib.request.urlopen(
                    f"http://{host}:{port}/minio/health/ready", timeout=2
                )
                break
            except (urllib.error.URLError, urllib.error.HTTPError):
                time.sleep(0.5)
        yield container
    finally:
        container.stop()


async def test_s3_object_store_round_trip(minio_container) -> None:
    """S3ObjectStore put/get/list/delete against MinIO."""
    from agentcook_storage import S3ObjectStore

    host = minio_container.get_container_host_ip()
    port = minio_container.get_exposed_port(9000)
    endpoint = f"http://{host}:{port}"

    # Create the bucket first via aioboto3 directly (S3ObjectStore doesn't
    # expose bucket creation — that's typically an ops-time action).
    import aioboto3

    session = aioboto3.Session(
        aws_access_key_id="minioadmin",
        aws_secret_access_key="minioadmin",
        region_name="us-east-1",
    )
    async with session.client("s3", endpoint_url=endpoint) as s3:
        await s3.create_bucket(Bucket="agentcook-test")

    store = S3ObjectStore(
        endpoint_url=endpoint,
        aws_access_key_id="minioadmin",
        aws_secret_access_key="minioadmin",
        region_name="us-east-1",
    )
    await store.put_object("agentcook-test", "k1.txt", b"hello agentcook")
    assert await store.get_object("agentcook-test", "k1.txt") == b"hello agentcook"

    keys = [k async for k in store.list_objects("agentcook-test")]
    assert "k1.txt" in keys

    url = await store.presigned_url("agentcook-test", "k1.txt", expires_in=60)
    assert url.startswith("http") and "k1.txt" in url

    await store.delete_object("agentcook-test", "k1.txt")
    keys_after = [k async for k in store.list_objects("agentcook-test")]
    assert "k1.txt" not in keys_after


# --------------------------- PostgresStore + PgVectorMemoryStore ------------

@pytest.fixture(scope="module")
def pgvector_container() -> Iterator[object]:
    """A Postgres container with the pgvector extension pre-installed.

    Spun up independently of Agent C's ``pg_container`` so this suite is
    not blocked on the root ``docker-compose`` image swap. Once C swaps
    the root fixture image to ``pgvector/pgvector:pg16``, this fixture
    can collapse into ``pg_container``.

    The TCP port is open as soon as Postgres starts initdb, but asyncpg
    will hit ``ConnectionRefusedError`` until the server actually begins
    accepting client connections — testcontainers' ``start()`` doesn't
    cover that gap. We poll until a plain TCP connect succeeds.
    """
    import asyncio
    import socket

    if not _docker_available():
        pytest.skip("Docker daemon not reachable; skipping PG integration tests")
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer("pgvector/pgvector:pg16")
    container.start()
    try:
        host = container.get_container_host_ip()
        port = int(container.get_exposed_port(5432))
        deadline = time.time() + 60
        while time.time() < deadline:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1.0)
                try:
                    sock.connect((host, port))
                    break
                except OSError:
                    time.sleep(0.5)
        else:
            raise RuntimeError(f"pgvector container did not accept TCP on {host}:{port}")

        # asyncpg requires the server to be past startup recovery too.
        dsn = container.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql://"
        )

        async def _ping() -> None:
            import asyncpg

            deadline2 = time.time() + 60
            while time.time() < deadline2:
                try:
                    conn = await asyncpg.connect(dsn)
                    await conn.execute("SELECT 1")
                    await conn.close()
                    return
                except Exception:
                    await asyncio.sleep(0.5)
            raise RuntimeError(f"pgvector did not accept asyncpg connection at {dsn}")

        asyncio.new_event_loop().run_until_complete(_ping())

        yield container
    finally:
        container.stop()


async def test_postgres_store_pgvector_round_trip(pgvector_container) -> None:
    """PostgresStore + pgvector + PgVectorMemoryStore end-to-end."""
    from agentcook_core import MemoryEvent
    from agentcook_storage import (
        PgVectorMemoryStore,
        PostgresStore,
        ensure_pgvector_extension,
    )

    dsn = pgvector_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://"
    )
    store = await PostgresStore.connect(dsn, min_size=1, max_size=2)
    try:
        await ensure_pgvector_extension(store)

        # A deterministic 3-D embedder so we can assert on similarity ordering.
        async def stub_embed(text: str) -> list[float]:
            mapping = {
                "pgvector is fast": [1.0, 0.0, 0.0],
                "redis is fast": [0.0, 1.0, 0.0],
                "search query about pgvector": [0.95, 0.05, 0.0],
            }
            return mapping.get(text, [0.0, 0.0, 1.0])

        memory = PgVectorMemoryStore(store, stub_embed, vector_dim=3)
        await memory.ensure_schema()

        await memory.append_event(
            "agent-it",
            MemoryEvent(
                timestamp="2026-05-19T10:00:00Z",
                kind="observation",
                content="pgvector is fast",
            ),
        )
        await memory.append_event(
            "agent-it",
            MemoryEvent(
                timestamp="2026-05-19T10:01:00Z",
                kind="observation",
                content="redis is fast",
            ),
        )

        events = await memory.stream_events("agent-it")
        assert len(events) == 2 and events[0].timestamp < events[1].timestamp

        recall = await memory.search(
            "agent-it",
            "search query about pgvector",
            top_k=2,
        )
        assert len(recall.hits) == 2
        # The pgvector-similar event should rank first.
        assert "pgvector" in recall.hits[0].content
        assert recall.hits[0].score > recall.hits[1].score
    finally:
        # Clean up table so re-runs in the same session don't accumulate.
        await store.execute("DROP TABLE IF EXISTS memory_events")
        await store.close()
