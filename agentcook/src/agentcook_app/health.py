"""Health endpoints.

- ``/health``       — liveness: the process is up (always 200).
- ``/health/ready`` — readiness: every *configured* dependency answers.

Readiness only checks what this deployment actually uses — Postgres when
``AGENTCOOK_STORAGE=postgres``, Redis when ``AGENTCOOK_REDIS_URL`` is set
— so an in-memory dev instance is ready without either, while a
production pod whose database is down is taken out of rotation.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


async def _check_postgres(container: Any) -> tuple[bool, str]:
    store = getattr(container, "_pg_store", None)
    if store is None:
        return False, "not connected"
    try:
        await asyncio.wait_for(store.fetchrow("SELECT 1"), timeout=3)
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


async def _check_redis(url: str) -> tuple[bool, str]:
    try:
        import redis.asyncio as aioredis
    except ImportError:
        return False, "redis package not installed"
    client = aioredis.Redis.from_url(url, socket_timeout=3)
    try:
        await client.ping()
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    finally:
        await client.aclose()


def setup_health(app: FastAPI) -> None:
    @app.get("/health", tags=["meta"], include_in_schema=False)
    async def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["meta"], include_in_schema=False)
    async def readiness(request: Request) -> JSONResponse:
        container = request.app.state.container
        settings = container.settings
        checks: dict[str, dict[str, str]] = {}
        if settings.storage == "postgres":
            ok, detail = await _check_postgres(container)
            checks["postgres"] = {"status": "up" if ok else "down", "detail": detail}
        if settings.redis_url:
            ok, detail = await _check_redis(settings.redis_url)
            checks["redis"] = {"status": "up" if ok else "down", "detail": detail}
        healthy = all(c["status"] == "up" for c in checks.values())
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={
                "status": "ready" if healthy else "not_ready",
                "checks": checks,
                "storage": settings.storage,
                "model": settings.llm_provider,
            },
        )


__all__ = ["setup_health"]
