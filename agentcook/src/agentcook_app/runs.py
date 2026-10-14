"""Run lifecycle — agent runs outlive the HTTP request that started them.

A chat turn may take tens of seconds (several model calls + tools). Tying
the run to the SSE connection means a flaky mobile network or a browser
tab switch aborts half-finished work and loses the transcript. Instead:

- each run is an ``asyncio.Task`` owned by the :class:`RunManager`;
- the SSE response is just a *subscriber* to the run's frame queue;
- if the client disconnects the run keeps going and its result is
  persisted, so reopening the session shows the full answer;
- an explicit cancel (the UI's Stop button) is the only way to abort;
- at most one active run per session (concurrent turns would interleave
  the transcript), and shutdown cancels runs cleanly.

:class:`DelegationLog` keeps recent sub-agent delegations for the
delegation-graph endpoint.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import logging
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

Frame = dict[str, Any]
_SENTINEL: Frame = {"__end__": True}


class SessionBusyError(RuntimeError):
    def __init__(self, session_id: str, run_id: str) -> None:
        super().__init__(f"session {session_id!r} already has an active run ({run_id})")
        self.session_id = session_id
        self.run_id = run_id


@dataclass(slots=True)
class RunHandle:
    run_id: str
    user_id: str
    session_id: str
    agent: str
    created_at: str
    queue: asyncio.Queue[Frame] = field(default_factory=asyncio.Queue)
    task: asyncio.Task[None] | None = None
    subscribed: bool = True
    status: str = "running"

    def emit(self, frame: Frame) -> None:
        if self.subscribed:
            self.queue.put_nowait(frame)

    def close(self) -> None:
        self.queue.put_nowait(_SENTINEL)

    async def frames(self, *, heartbeat: float = 15.0) -> AsyncIterator[Frame | None]:
        """Yield frames until the run ends; ``None`` = heartbeat tick."""
        try:
            while True:
                try:
                    frame = await asyncio.wait_for(self.queue.get(), timeout=heartbeat)
                except TimeoutError:
                    yield None
                    continue
                if frame is _SENTINEL:
                    return
                yield frame
        finally:
            # Consumer went away (disconnect) or finished — stop buffering.
            self.subscribed = False


class RunManager:
    def __init__(self, *, max_runs: int = 1_000) -> None:
        self._runs: dict[str, RunHandle] = {}
        self._by_session: dict[str, str] = {}
        self._max_runs = max_runs

    def get(self, run_id: str) -> RunHandle | None:
        return self._runs.get(run_id)

    def active_for_session(self, session_id: str) -> RunHandle | None:
        run_id = self._by_session.get(session_id)
        return self._runs.get(run_id) if run_id else None

    @property
    def active_count(self) -> int:
        return len(self._runs)

    def start(
        self,
        *,
        run_id: str,
        user_id: str,
        session_id: str,
        agent: str,
        body: Callable[[RunHandle], Awaitable[None]],
    ) -> RunHandle:
        existing = self.active_for_session(session_id)
        if existing is not None:
            raise SessionBusyError(session_id, existing.run_id)
        if len(self._runs) >= self._max_runs:
            raise RuntimeError("too many concurrent agent runs")
        handle = RunHandle(
            run_id=run_id,
            user_id=user_id,
            session_id=session_id,
            agent=agent,
            created_at=dt.datetime.now(tz=dt.UTC).isoformat(timespec="seconds"),
        )
        self._runs[run_id] = handle
        self._by_session[session_id] = run_id

        async def runner() -> None:
            try:
                await body(handle)
            except asyncio.CancelledError:
                handle.status = "cancelled"
                raise
            except Exception:
                handle.status = "failed"
                logger.exception("run %s crashed", run_id)
            finally:
                if handle.status == "running":
                    handle.status = "finished"
                handle.close()
                self._runs.pop(run_id, None)
                if self._by_session.get(session_id) == run_id:
                    self._by_session.pop(session_id, None)

        handle.task = asyncio.create_task(runner(), name=f"agent-run-{run_id}")
        return handle

    def cancel(self, run_id: str, *, user_id: str) -> bool:
        handle = self._runs.get(run_id)
        if handle is None or handle.user_id != user_id or handle.task is None:
            return False
        handle.task.cancel()
        return True

    async def shutdown(self, timeout: float = 5.0) -> None:
        tasks = [h.task for h in self._runs.values() if h.task is not None]
        for task in tasks:
            task.cancel()
        if tasks:
            with contextlib.suppress(Exception):
                await asyncio.wait(tasks, timeout=timeout)


class DelegationLog:
    """Recent sub-agent delegations (bounded ring buffer)."""

    def __init__(self, capacity: int = 500) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=capacity)

    def record(self, events: list[dict[str, Any]], *, session_id: str, user_id: str) -> None:
        for event in events:
            self._events.append({**event, "session_id": session_id, "user_id": user_id})

    def for_agent(
        self, agent: str, *, user_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        matches = [
            e
            for e in self._events
            if (e.get("from") == agent or e.get("to") == agent)
            and (user_id is None or e.get("user_id") == user_id)
        ]
        return matches[-limit:]


__all__ = ["DelegationLog", "RunHandle", "RunManager", "SessionBusyError"]
