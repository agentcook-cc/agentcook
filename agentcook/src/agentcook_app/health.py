"""Health check endpoints for agentcook FastAPI runtime.

Phase 2 Day 20 — Agent C.

Two endpoints:
- ``/health``       — liveness probe (always 200 if process is alive)
- ``/health/ready`` — readiness probe (checks postgres + redis connectivity)

Usage in ``main.py``::

    from agentcook_app.health import setup_health
    # inside create_app():
    setup_health(app)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI


def _pg_dsn() -> str:
    return os.environ.get(
        "AGENTCOOK_DATABASE_URL",
        "postgresql://agentcook:agentcook@localhost:5432/agentcook",
    )


def _redis_url() -> str:
    return os.environ.get("AGENTCOOK_REDIS_URL", "redis://localhost:6379/0")


async def _check_postgres() -> tuple[bool, str]:
    """Attempt a simple SELECT 1 against postgres."""
    try:
        import asyncpg

        conn = await asyncpg.connect(_pg_dsn(), timeout=3)
        await conn.execute("SELECT 1")
        await conn.close()
        return True, "ok"
    except ImportError:
        # asyncpg not installed — try psycopg sync fallback
        try:
            import psycopg

            with psycopg.connect(_pg_dsn(), connect_timeout=3) as conn:
                conn.execute("SELECT 1")
            return True, "ok"
        except Exception as exc:
            return False, f"psycopg: {exc}"
    except Exception as exc:
        return False, f"asyncpg: {exc}"


async def _check_redis() -> tuple[bool, str]:
    """Attempt a PING against redis."""
    try:
        import redis

        client = redis.Redis.from_url(_redis_url(), socket_timeout=3)
        client.ping()
        client.close()
        return True, "ok"
    except ImportError:
        return False, "redis package not installed"
    except Exception as exc:
        return False, str(exc)


def setup_health(app: FastAPI) -> None:
    """Register /health and /health/ready endpoints."""
    from fastapi.responses import JSONResponse

    @app.get("/health", tags=["meta"], include_in_schema=False)
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["meta"], include_in_schema=False)
    async def readiness() -> JSONResponse:
        pg_ok, pg_msg = await _check_postgres()
        redis_ok, redis_msg = await _check_redis()

        checks = {
            "postgres": {"status": "up" if pg_ok else "down", "detail": pg_msg},
            "redis": {"status": "up" if redis_ok else "down", "detail": redis_msg},
        }

        all_healthy = pg_ok and redis_ok
        status_code = 200 if all_healthy else 503

        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ready" if all_healthy else "not_ready",
                "checks": checks,
            },
        )
