"""Live log stream — ``GET /api/v1/logs/stream`` (SSE).

Frames come from the in-process :class:`~agentcook_app.log_stream.LogHub`
(structlog + stdlib logging), shaped as :class:`LogFrame`.

- ``follow=false`` (default): a snapshot — the most recent ``limit``
  frames, the last one marked ``extra.finished = true`` (the v1 contract
  the admin ``LogStreamView`` closes on). Never blocks.
- ``follow=true``: replays the last ``history`` frames, then tails new
  log lines indefinitely with ``: ping`` keep-alives every 15s.

Requires an authenticated admin in ``required`` auth mode: log lines can
contain request paths and user ids.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from agentcook_app.container import AppContainer, get_container
from agentcook_app.log_stream import LogHub, _passes
from agentcook_app.schemas import ErrorEnvelope
from agentcook_app.schemas_logs import LogLevel
from agentcook_app.security import UserContext, get_current_user

router = APIRouter(prefix="/api/v1/logs", tags=["logs"])

_DEFAULT_LIMIT = 30
_MAX_LIMIT = 500


def _encode(frame: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(frame, ensure_ascii=False, default=str)}\n\n".encode()


async def _snapshot(hub: LogHub, *, limit: int, level: str | None) -> AsyncIterator[bytes]:
    frames = hub.recent(limit, min_level=level)
    if not frames:
        frames = [
            {
                "timestamp": dt.datetime.now(tz=dt.UTC).isoformat(timespec="milliseconds"),
                "level": "info",
                "event": "log.stream.empty",
                "request_id": None,
                "logger": "agentcook_app.logs",
                "extra": {},
            }
        ]
    for index, frame in enumerate(frames):
        if index == len(frames) - 1:
            frame = {**frame, "extra": {**frame["extra"], "finished": True}}
        yield _encode(frame)


async def _follow(hub: LogHub, *, history: int, level: str | None) -> AsyncIterator[bytes]:
    subscription = hub.subscribe()
    # Prime the subscription before replaying so nothing slips between.
    next_frame: asyncio.Future[dict[str, Any]] = asyncio.ensure_future(subscription.__anext__())
    try:
        for frame in hub.recent(history, min_level=level) if history else []:
            yield _encode(frame)
        while True:
            done, _ = await asyncio.wait({next_frame}, timeout=15)
            if not done:
                yield b": ping\n\n"
                continue
            frame = next_frame.result()
            next_frame = asyncio.ensure_future(subscription.__anext__())
            if _passes(frame, level):
                yield _encode(frame)
    finally:
        next_frame.cancel()
        await subscription.aclose()


@router.get(
    "/stream",
    responses={
        200: {"description": "SSE stream of log frames.", "content": {"text/event-stream": {}}},
        403: {"model": ErrorEnvelope},
    },
    summary="Stream live log frames as Server-Sent Events",
)
async def stream_logs(
    limit: int = Query(
        default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT, description="Snapshot size (follow=false)."
    ),
    history: int = Query(
        default=_DEFAULT_LIMIT, ge=0, le=_MAX_LIMIT, description="Frames replayed before tailing."
    ),
    follow: bool = Query(default=False, description="Keep streaming new lines."),
    level: LogLevel | None = Query(default=None, description="Minimum level."),
    container: AppContainer = Depends(get_container),
    user: UserContext = Depends(get_current_user),
) -> StreamingResponse:
    if container.settings.auth_mode == "required" and not user.is_admin:
        raise HTTPException(
            status_code=403,
            detail=ErrorEnvelope(
                code="AUTH_FORBIDDEN", message="Admin scope required."
            ).model_dump(),
        )
    body = (
        _follow(container.log_hub, history=history, level=level)
        if follow
        else _snapshot(container.log_hub, limit=limit, level=level)
    )
    return StreamingResponse(
        body,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


__all__ = ["router"]
