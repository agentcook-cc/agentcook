"""Memory API endpoints — Day 13 real implementation.

Wires the 7 endpoints from the Day 13 brief to ``AgentRuntime`` via
``Depends(get_runtime)`` so the in-memory implementation drives Day 13
and the Phase 2 ``PgRuntime`` can drop in by overriding the dependency.

We additionally keep ``GET /agents/{id}/soul`` (latest version) — the
admin first-screen will hit it on every load and the alternative
``GET /soul/history?limit=1`` is needlessly chatty. Flagged in the Day 13
progress report so the author can prune later if undesired.

Wire format conforms to frontend-conventions §7.6: errors are the flat
``{code, message, detail}`` envelope produced by ``errors.install()`` —
endpoints raise typed exceptions and the central handler shapes them.
"""

from __future__ import annotations

import datetime as dt

from agentcook_core import IdentityCard, MemoryEvent, SoulConfig
from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, Response, status

from agentcook_app.observability import enrich_current_span
from agentcook_app.schemas import (
    ErrorEnvelope,
    FlushRequest,
    FlushResponse,
    IdentityResponse,
    MemoryEventCreate,
    MemoryEventKindLit,
    MemoryEventListResponse,
    MemoryEventResponse,
    MemoryHitResponse,
    SearchRequest,
    SearchResponse,
    SoulConfigBody,
    SoulHistoryResponse,
    SoulResponse,
    SoulVersionResponse,
)
from agentcook_app.security import UserContext, verify_access_token
from agentcook_app.services import (
    AgentNotFoundError,
    AgentRuntime,
    SoulNotInitializedError,
    SoulVersion,
    StoredMemoryEvent,
    get_runtime,
)

router = APIRouter(prefix="/api/v1/agents", tags=["memory"])

AGENT_ID_PATH = Path(
    ...,
    description="Agent identifier",
    pattern=r"^[A-Za-z0-9_\-]{1,64}$",
)

EVENT_ID_PATH = Path(..., pattern=r"^[A-Za-z0-9_\-]{1,64}$")

_COMMON_ERRORS = {
    400: {"model": ErrorEnvelope, "description": "Malformed request body (e.g. invalid JSON)."},
    401: {"model": ErrorEnvelope, "description": "Missing or invalid access token."},
    403: {"model": ErrorEnvelope, "description": "Authenticated user lacks required scope."},
    404: {"model": ErrorEnvelope, "description": "Agent not found."},
    405: {"model": ErrorEnvelope, "description": "HTTP method not allowed on this path."},
    422: {"model": ErrorEnvelope, "description": "Path / query / body validation failed."},
    500: {"model": ErrorEnvelope, "description": "Internal server error."},
}


# --------------------------------------------------------------------------
# Adapters: service value-types → wire schemas
# --------------------------------------------------------------------------


def _identity_card_to_resp(card: IdentityCard) -> IdentityResponse:
    return IdentityResponse(
        name=card.name,
        role=card.role,
        created_at=card.created_at,
        scopes=sorted(card.scopes),
        metadata=dict(card.metadata),
    )


def _soul_to_resp(config: SoulConfig) -> SoulResponse:
    return SoulResponse(
        tone=config.tone,
        language_style=config.language_style,
        values=list(config.values),
        custom_traits=dict(config.custom_traits),
    )


def _soul_version_to_resp(v: SoulVersion) -> SoulVersionResponse:
    return SoulVersionResponse(
        version=v.version,
        created_at=v.created_at,
        config=SoulConfigBody(
            tone=v.config.tone,
            language_style=v.config.language_style,
            values=list(v.config.values),
            custom_traits=dict(v.config.custom_traits),
        ),
    )


def _stored_event_to_resp(stored: StoredMemoryEvent) -> MemoryEventResponse:
    return MemoryEventResponse(
        id=stored.id,
        timestamp=stored.event.timestamp,
        kind=stored.event.kind,
        content=stored.event.content,
        source=stored.event.source,
        metadata=dict(stored.event.metadata),
    )


def _now_iso() -> str:
    return dt.datetime.now(tz=dt.UTC).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# Identity (read-only — ADR-011 Layer 1, immutable)
# --------------------------------------------------------------------------


@router.get(
    "/{agent_id}/identity",
    response_model=IdentityResponse,
    responses=_COMMON_ERRORS,
    summary="Read an Agent's immutable identity card (ADR-011 layer 1).",
)
async def get_identity(
    agent_id: str = AGENT_ID_PATH,
    user: UserContext = Depends(verify_access_token),
    runtime: AgentRuntime = Depends(get_runtime),
) -> IdentityResponse:
    enrich_current_span(user_id=user.user_id, agent_id=agent_id)
    card = await runtime.get_identity(agent_id)
    return _identity_card_to_resp(card)


# --------------------------------------------------------------------------
# Soul (read latest + append new version + read history)
# --------------------------------------------------------------------------


@router.get(
    "/{agent_id}/soul",
    response_model=SoulResponse,
    responses=_COMMON_ERRORS,
    summary="Read the current (latest) SoulConfig version.",
)
async def get_soul_latest(
    agent_id: str = AGENT_ID_PATH,
    user: UserContext = Depends(verify_access_token),
    runtime: AgentRuntime = Depends(get_runtime),
) -> SoulResponse:
    enrich_current_span(user_id=user.user_id, agent_id=agent_id)
    version = await runtime.get_soul_latest(agent_id)
    return _soul_to_resp(version.config)


@router.post(
    "/{agent_id}/soul",
    response_model=SoulVersionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        **_COMMON_ERRORS,
        412: {
            "model": ErrorEnvelope,
            "description": "X-Confirm-Identity-Change header required to mutate Soul.",
        },
    },
    summary="Append a new SoulConfig version (ADR-011 layer 2, append-only).",
)
async def append_soul(
    body: SoulConfigBody,
    agent_id: str = AGENT_ID_PATH,
    x_confirm_identity_change: bool | None = Header(default=None),
    user: UserContext = Depends(verify_access_token),
    runtime: AgentRuntime = Depends(get_runtime),
) -> SoulVersionResponse:
    if x_confirm_identity_change is not True:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=ErrorEnvelope(
                code="CONFIRMATION_REQUIRED",
                message="Mutating Soul requires X-Confirm-Identity-Change: true.",
            ).model_dump(),
        )
    new_version = await runtime.append_soul(
        agent_id,
        SoulConfig(
            tone=body.tone,
            language_style=body.language_style,
            values=tuple(body.values),
            custom_traits=dict(body.custom_traits),
        ),
    )
    return _soul_version_to_resp(new_version)


@router.get(
    "/{agent_id}/soul/history",
    response_model=SoulHistoryResponse,
    responses=_COMMON_ERRORS,
    summary="List all SoulConfig versions (oldest → newest), capped.",
)
async def list_soul_history(
    agent_id: str = AGENT_ID_PATH,
    limit: int = Query(default=50, ge=1, le=200),
    user: UserContext = Depends(verify_access_token),
    runtime: AgentRuntime = Depends(get_runtime),
) -> SoulHistoryResponse:
    versions = await runtime.list_soul_history(agent_id, limit=limit)
    return SoulHistoryResponse(items=[_soul_version_to_resp(v) for v in versions])


# --------------------------------------------------------------------------
# Memory events (append + list)
# --------------------------------------------------------------------------


@router.post(
    "/{agent_id}/memory/events",
    response_model=MemoryEventResponse,
    status_code=status.HTTP_201_CREATED,
    responses=_COMMON_ERRORS,
    summary="Append a memory event (ADR-011 layer 3 event stream).",
)
async def append_memory_event(
    body: MemoryEventCreate,
    agent_id: str = AGENT_ID_PATH,
    user: UserContext = Depends(verify_access_token),
    runtime: AgentRuntime = Depends(get_runtime),
) -> MemoryEventResponse:
    stored = await runtime.append_memory_event(
        agent_id,
        MemoryEvent(
            timestamp=body.timestamp or _now_iso(),
            kind=body.kind,
            content=body.content,
            source=body.source,
            metadata=dict(body.metadata),
        ),
    )
    return _stored_event_to_resp(stored)


@router.get(
    "/{agent_id}/memory/events",
    response_model=MemoryEventListResponse,
    responses=_COMMON_ERRORS,
    summary="List memory events (cursor pagination, oldest → newest within page).",
)
async def list_memory_events(
    agent_id: str = AGENT_ID_PATH,
    since: str | None = Query(default=None, description="ISO-8601 UTC lower bound."),
    kind: MemoryEventKindLit | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    user: UserContext = Depends(verify_access_token),
    runtime: AgentRuntime = Depends(get_runtime),
) -> MemoryEventListResponse:
    items, next_cursor = await runtime.list_memory_events(
        agent_id, since=since, kind=kind, limit=limit, cursor=cursor
    )
    return MemoryEventListResponse(
        items=[_stored_event_to_resp(s) for s in items],
        next_cursor=next_cursor,
    )


# --------------------------------------------------------------------------
# Semantic recall (v1 cosine; hybrid BM25 fusion Day 22)
# --------------------------------------------------------------------------


@router.post(
    "/{agent_id}/memory/search",
    response_model=SearchResponse,
    responses=_COMMON_ERRORS,
    summary="Semantic recall (v1 cosine; hybrid BM25 fusion Day 22).",
)
async def search_memory(
    body: SearchRequest,
    agent_id: str = AGENT_ID_PATH,
    user: UserContext = Depends(verify_access_token),
    runtime: AgentRuntime = Depends(get_runtime),
) -> SearchResponse:
    recall = await runtime.search_memory(agent_id, body.query, top_k=body.top_k)
    return SearchResponse(
        query=recall.query,
        hits=[
            MemoryHitResponse(
                content=hit.content,
                score=hit.score,
                event=(
                    MemoryEventResponse(
                        id=str(hit.metadata.get("id", "")),
                        timestamp=hit.event.timestamp,
                        kind=hit.event.kind,
                        content=hit.event.content,
                        source=hit.event.source,
                        metadata=dict(hit.event.metadata),
                    )
                    if hit.event is not None
                    else None
                ),
            )
            for hit in recall.hits
        ],
    )


# --------------------------------------------------------------------------
# Memory flush (destructive, double-confirm)
# --------------------------------------------------------------------------


@router.post(
    "/{agent_id}/memory/flush",
    response_model=FlushResponse,
    responses={
        **_COMMON_ERRORS,
        422: {
            "model": ErrorEnvelope,
            "description": "Confirm string missing or wrong.",
        },
    },
    summary="Flush memory events; Identity preserved (immutable). Soul optionally preserved.",
)
async def flush_memory(
    body: FlushRequest,
    agent_id: str = AGENT_ID_PATH,
    user: UserContext = Depends(verify_access_token),
    runtime: AgentRuntime = Depends(get_runtime),
) -> FlushResponse:
    result = await runtime.flush_memory(
        agent_id, preserve_identity_and_soul=body.preserve_identity_and_soul
    )
    return FlushResponse(
        deleted_event_count=result.deleted_event_count,
        identity_preserved=result.identity_preserved,
        soul_preserved=result.soul_preserved,
    )


# --------------------------------------------------------------------------
# Exception → HTTP mapping (registered on app startup by errors.install)
# --------------------------------------------------------------------------


def _agent_not_found_handler(_request, exc: AgentNotFoundError) -> Response:
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=ErrorEnvelope(
            code="AGENT_NOT_FOUND",
            message=str(exc),
            detail={"agent_id": exc.agent_id},
        ).model_dump(),
    )


def _soul_not_init_handler(_request, exc: SoulNotInitializedError) -> Response:
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=ErrorEnvelope(
            code="SOUL_NOT_INITIALIZED",
            message=str(exc),
            detail={"agent_id": exc.agent_id},
        ).model_dump(),
    )


def install_exception_handlers(app) -> None:
    app.add_exception_handler(AgentNotFoundError, _agent_not_found_handler)
    app.add_exception_handler(SoulNotInitializedError, _soul_not_init_handler)


__all__ = ["install_exception_handlers", "router"]
