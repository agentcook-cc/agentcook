"""Monorepo-wide pytest fixtures.

Shared by all packages (agentcook-core / providers / storage / agentcook).
- `unit` marker: pure-Python tests, no Docker.
- `integration` marker: spins up testcontainers PostgreSQL + Redis.

The `pg_container` / `redis_container` fixtures are session-scoped — one
container per `pytest` invocation, shared across packages. Per-test isolation
is achieved by `db_session` (truncates) / `redis_client` (FLUSHDB).

Engineers writing unit tests don't need Docker — they don't request these
fixtures, and they don't pay the startup cost.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

# testcontainers 默认 mount host 端 docker.sock 路径到 ryuk 容器,但在 colima
# / Lima / 远程 daemon 等"daemon 路径 ≠ host 路径"的环境下挂载会失败。
# 把它强制成 daemon VM 内部的标准路径 /var/run/docker.sock,所有运行时
# (colima、Docker Desktop、Linux 原生)都能用。
os.environ.setdefault("TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE", "/var/run/docker.sock")

# docker-py (used by testcontainers) does not read `docker context` — it falls
# back to /var/run/docker.sock when DOCKER_HOST is unset. On colima (default
# install on macOS) the socket lives at ~/.colima/default/docker.sock instead,
# so the SDK can't reach the daemon and every integration test SKIPs.
# This is a *runtime* detection — we never write to host config files.
#
# Edge case: a stale socket file from a previous daemon (Docker Desktop) can
# linger at /var/run/docker.sock — the file passes S_ISSOCK but nothing is
# listening, so docker-py raises ConnectionRefused. The only reliable test is
# to try pinging each candidate and pick the first that answers.
def _ping(sock_path: str) -> bool:
    try:
        import docker as _docker

        c = _docker.DockerClient(base_url=f"unix://{sock_path}", timeout=2)
        c.ping()
        return True
    except Exception:
        return False


if "DOCKER_HOST" not in os.environ:
    _standard_sock = "/var/run/docker.sock"
    _colima_sock = os.path.expanduser("~/.colima/default/docker.sock")
    if not _ping(_standard_sock) and _ping(_colima_sock):
        os.environ["DOCKER_HOST"] = f"unix://{_colima_sock}"


def _docker_available() -> bool:
    """Best-effort check that a Docker daemon is reachable.

    testcontainers raises a noisy error if the daemon is down. We
    short-circuit with a clear skip so unit tests still pass on machines
    without Docker. Existence of `docker.sock` on disk is not enough — old
    sockets get left behind by stopped daemons (colima, Docker Desktop) — so
    we issue an actual ping.
    """
    try:
        import docker

        client = docker.from_env(timeout=2)
        client.ping()
        return True
    except Exception:  # pragma: no cover — defensive
        return False


@pytest.fixture(scope="session")
def pg_container() -> Iterator[object]:
    """Session-scoped PostgreSQL container for integration tests."""
    if not _docker_available():
        pytest.skip("Docker daemon not reachable; skipping PG integration fixture")
    from testcontainers.postgres import PostgresContainer

    # pgvector image keeps unit tests honest: ADR-011 says PostgresStore uses
    # pgvector → integration tests must hit a PG that actually has the extension.
    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        yield pg


@pytest.fixture(scope="session")
def redis_container() -> Iterator[object]:
    """Session-scoped Redis container for integration tests."""
    if not _docker_available():
        pytest.skip("Docker daemon not reachable; skipping Redis integration fixture")
    from testcontainers.redis import RedisContainer

    with RedisContainer("redis:7-alpine") as r:
        yield r


@pytest.fixture
def pg_url(pg_container) -> str:
    """SQLAlchemy-style PostgreSQL URL for the running container."""
    return pg_container.get_connection_url()


@pytest.fixture
def db_session(pg_container) -> Iterator[object]:
    """Per-test psycopg connection. Caller is responsible for txn isolation."""
    import psycopg

    dsn = pg_container.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
    with psycopg.connect(dsn) as conn:
        yield conn
        conn.rollback()


@pytest.fixture
def redis_client(redis_container) -> Iterator[object]:
    """Per-test Redis client. FLUSHDB before yielding to guarantee clean state."""
    import redis

    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    client = redis.Redis(host=host, port=int(port), decode_responses=True)
    client.flushdb()
    yield client
    client.close()
