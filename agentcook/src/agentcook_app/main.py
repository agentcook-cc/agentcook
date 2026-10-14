"""agentcook FastAPI runtime — application factory.

Per ADR-013 this app is the **runtime side** of the dual-backend split:

- it *verifies* JWT access tokens (agentcook-java issues them);
- it runs agents: the agent loop, tools, skills, sub-agent delegation,
  conversation transcripts and long-term memory;
- it does NOT own users, permissions, plugin packages or audit logs.

``create_app()`` builds everything from :class:`Settings` (environment)
unless a test passes explicit ``settings`` / ``container``. The module
level ``app`` exists for ``uvicorn agentcook_app.main:app``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agentcook_app import errors, logging_config
from agentcook_app.config import Settings
from agentcook_app.container import AppContainer
from agentcook_app.health import setup_health
from agentcook_app.metrics import setup_metrics
from agentcook_app.observability import setup_telemetry
from agentcook_app.routers import (
    agents,
    chat,
    conversations,
    delegations,
    logs,
    memory,
    skills,
)

API_DESCRIPTION = """\
Agent runtime for AgentCook: a streaming agent loop with tools, skills,
sub-agent delegation, conversation transcripts and long-term memory.

* **Chat** — `POST /api/v1/chat/stream` runs one agent turn and streams
  typed frames (text deltas, tool calls, tool results, usage).
* **Conversations** — transcripts per user, replayed on every turn.
* **Agents / toolkits / skills** — what the runtime can do, as data.
* **Memory** — identity / soul / long-term memory per agent instance.

Authentication: `Authorization: Bearer <JWT>` issued by agentcook-java
(ADR-013). Errors use the `{code, message, detail}` envelope.
"""


_ENVELOPE_REF = {"$ref": "#/components/schemas/ErrorEnvelope"}


def _install_spec_metadata(app: FastAPI) -> None:
    """Make the generated spec truthful + stamp metadata for codegen / Pact.

    FastAPI documents request-validation failures with its own
    ``HTTPValidationError`` schema, but :mod:`agentcook_app.errors` turns
    every 422 into the canonical ``{code, message, detail}`` envelope —
    so the spec is rewritten to say what the API actually returns.
    """
    original = app.openapi

    def _patched() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema
        schema = original()
        for operations in schema.get("paths", {}).values():
            for operation in operations.values():
                responses = operation.get("responses", {})
                if "422" in responses:
                    responses["422"] = {
                        "description": "Request validation failed.",
                        "content": {"application/json": {"schema": _ENVELOPE_REF}},
                    }
        components = schema.get("components", {}).get("schemas", {})
        components.pop("HTTPValidationError", None)
        components.pop("ValidationError", None)
        info = schema.setdefault("info", {})
        info["x-frozen"] = "2026-10-14"
        info["x-scope"] = "python-runtime"
        info["x-paired-spec"] = "docs/api/java-v1.yaml"
        info["x-changelog"] = "docs/api/CHANGELOG.md"
        app.openapi_schema = schema
        return schema

    app.openapi = _patched  # type: ignore[method-assign]


def create_app(
    settings: Settings | None = None,
    *,
    container: AppContainer | None = None,
) -> FastAPI:
    """Build the FastAPI application.

    Args:
        settings: Configuration; defaults to :meth:`Settings.from_env`.
        container: Pre-built services (tests inject fakes here).
    """
    settings = settings or (container.settings if container else Settings.from_env())
    logging_config.configure(settings.log_level)
    container = container or AppContainer(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await container.start()
        try:
            yield
        finally:
            await container.stop()

    app = FastAPI(
        title="agentcook runtime",
        version=settings.version,
        description=API_DESCRIPTION,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.container = container
    _install_spec_metadata(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    setup_telemetry(app, settings.otel_endpoint)
    setup_metrics(app)
    setup_health(app)

    logging_config.install_request_context(app)
    errors.install(app)
    memory.install_exception_handlers(app)

    app.include_router(chat.router)
    app.include_router(conversations.router)
    app.include_router(agents.router)
    app.include_router(skills.router)
    app.include_router(delegations.router)
    app.include_router(memory.router)
    app.include_router(logs.router)
    return app


app = create_app()


__all__ = ["app", "create_app"]
