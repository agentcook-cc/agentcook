"""agentcook FastAPI runtime — Memory API entry point.

Per ADR-013 this app is the **runtime side** of the dual-backend split:
- We *verify* JWT access tokens; we don't issue them (Java owns auth).
- We expose Agent runtime + Memory + (later) chat / multi-agent loops.
- We do NOT own User / Permission / Connector / Audit Log (Java).

The CORS allowlist defaults to admin (`5173`) + app (`5174`) dev
servers and the docs origin; production deploys override via env.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentcook_app import errors, logging_config
from agentcook_app.metrics import setup_metrics
from agentcook_app.observability import setup_telemetry
from agentcook_app.routers import memory


def _cors_origins() -> list[str]:
    if origins := os.environ.get("AGENTCOOK_CORS_ORIGINS"):
        return [o.strip() for o in origins.split(",") if o.strip()]
    return [
        "http://localhost:5173",  # admin (Vue) dev
        "http://localhost:5174",  # app (React) dev
        "http://localhost:3000",  # docs / generic dev
    ]


def create_app() -> FastAPI:
    """FastAPI factory — exposed for tests and ``scripts/dump-openapi.py``."""
    logging_config.configure(os.environ.get("AGENTCOOK_LOG_LEVEL", "INFO"))

    app = FastAPI(
        title="agentcook runtime",
        version="0.1.0",
        description=(
            "Agent runtime + Memory API. JWT verification only — token issuance "
            "lives in agentcook-java (ADR-013). Wire format conforms to "
            "frontend-conventions §7.6."
        ),
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    setup_telemetry(app)
    setup_metrics(app)

    logging_config.install_request_context(app)
    errors.install(app)
    memory.install_exception_handlers(app)

    app.include_router(memory.router)

    @app.get("/healthz", tags=["meta"], include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


__all__ = ["app", "create_app"]
