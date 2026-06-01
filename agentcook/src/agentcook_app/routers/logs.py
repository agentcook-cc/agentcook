"""Logs streaming endpoint — Day 30 scaffolding (Phase 3 Day 5).

**Status**: scaffolding only. **Not wired** into ``main.py`` yet.
Day 31 wires this in alongside ``routers/delegations.py`` (which has
been waiting since Day 29) — both ride the same v1.1 → v1.2 minor
bump so the spec bump is amortized across two new endpoints.

What ships today:

- ``GET /api/v1/logs/stream`` — SSE-streamed log frames for B's
  ``LogStreamView`` (Day 31 admin monitoring page). Today's mock
  generates 30 synthetic frames over ~30s; Phase 5 swaps the body for
  a structlog broadcast handler so live logs from
  ``logging_config.configure()`` reach the browser.

The frame shape (``schemas_logs.LogFrame``) intentionally mirrors what
``logging_config.py`` already emits — when Phase 5 lands, the live
handler can ``yield LogFrame.model_validate(record)`` without any
schema-level translation.

Day 31 v1.2.0 bump SOP — covers BOTH this router AND
``routers/delegations.py``:

1. ``main.py``: ``from agentcook_app.routers import memory, skills, delegations, logs``
   + ``app.include_router(delegations.router)``
   + ``app.include_router(logs.router)``
2. ``main.py``: ``version="1.1.0"`` → ``"1.2.0"``
3. ``main.py``: ``_install_freeze_metadata`` x-frozen → Day 31 date
4. ``uv run python scripts/dump-openapi.py``
   expect: 11 paths (was 9), ~24 schemas (was 20)
5. Flip BOTH spec-freeze invariants:
   - ``test_delegations_router::TestSpecFreezeBoundary`` (Day 29 lock)
   - ``test_logs_router::TestSpecFreezeBoundary`` (Day 30 lock)
   into "must BE in" + version 1.2.0 assertions
6. ``docs/api/CHANGELOG.md`` prepend ``## v1.yaml — python-runtime v1.2.0``
7. Broadcast: B re-runs ``pnpm gen:api:python``; C re-runs
   ``make test-contract``

Two endpoints in one bump > two bumps a day apart — keeps B's
codegen / C's Pact reverify cadence at one cycle per Phase 3 day.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from agentcook_app.schemas_logs import LogFrame

router = APIRouter(prefix="/api/v1/logs", tags=["logs"])


# --------------------------------------------------------------------------
# Mock generator — replaced by structlog broadcast handler in Phase 5
# --------------------------------------------------------------------------


_MOCK_FRAME_INTERVAL_SECS = 1.0
_MOCK_DEFAULT_LIMIT = 30
_MOCK_MAX_LIMIT = 200

_LEVELS = ("info", "info", "info", "debug", "warning", "info", "error")
_EVENTS = (
    "request.start",
    "request.end",
    "agent.run",
    "model.select",
    "memory.write",
    "tool.invoke",
    "hook.fired",
)


def _build_frame(seq: int) -> LogFrame:
    """Synthesize one realistic-looking log line for the SSE mock."""
    now = dt.datetime.now(dt.UTC).isoformat()
    level = _LEVELS[seq % len(_LEVELS)]
    event = _EVENTS[seq % len(_EVENTS)]
    return LogFrame(
        timestamp=now,
        level=level,  # type: ignore[arg-type]
        event=event,
        request_id=f"{seq:08x}{seq:08x}",
        logger="agentcook_app.mock",
        extra={"seq": seq},
    )


async def _stream_log_frames(limit: int) -> AsyncIterator[bytes]:
    """Yield ``limit`` SSE frames pacing roughly one per second.

    SSE wire format: ``data: {json}\\n\\n``. The terminal frame carries
    ``finished: true`` (in ``extra``) so B's LogStreamView can close
    the EventSource cleanly.
    """
    for i in range(limit):
        finished = i == limit - 1
        frame = _build_frame(i)
        # Stuff the closure marker into ``extra`` so the schema stays clean.
        frame_dict = frame.model_dump()
        if finished:
            frame_dict["extra"] = {**frame_dict["extra"], "finished": True}
        yield f"data: {json.dumps(frame_dict, ensure_ascii=False)}\n\n".encode()
        if not finished:
            await asyncio.sleep(_MOCK_FRAME_INTERVAL_SECS)


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------


@router.get(
    "/stream",
    responses={
        200: {
            "description": "SSE stream of log frames.",
            "content": {"text/event-stream": {}},
        }
    },
    summary="Stream recent log frames as Server-Sent Events",
)
async def stream_logs(
    limit: int = Query(
        default=_MOCK_DEFAULT_LIMIT,
        ge=1,
        le=_MOCK_MAX_LIMIT,
        description="How many frames to emit before closing the stream.",
    ),
) -> StreamingResponse:
    return StreamingResponse(
        _stream_log_frames(limit),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
