"""In-process log broadcast — the source behind ``GET /api/v1/logs/stream``.

Both logging stacks feed one :class:`LogHub`:

- **structlog** events via :func:`structlog_processor` (inserted into the
  processor chain before rendering), and
- **stdlib logging** records (``agentcook_core``, uvicorn, libraries) via
  :class:`LogHubHandler` on the root logger.

The hub keeps a bounded ring buffer (so a newly opened admin page sees
recent history) and fans out to any number of subscribers through
bounded queues; a slow subscriber drops frames instead of applying
back-pressure to the request path. Secrets are never logged by design,
but values under sensitive-looking keys are redacted defensively.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import re
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

_LEVELS = {"debug", "info", "warning", "error", "critical"}
_SENSITIVE = re.compile(r"(authorization|token|secret|password|api[_-]?key|cookie)", re.I)
_RESERVED = {
    "event",
    "level",
    "timestamp",
    "request_id",
    "logger",
    "log_level",
    "_record",
    "_from_structlog",
}


def _normalize_level(level: Any) -> str:
    name = str(level or "info").lower()
    if name == "warn":
        name = "warning"
    if name == "exception":
        name = "error"
    return name if name in _LEVELS else "info"


def _safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)[:500]


class LogHub:
    """Bounded ring buffer + pub/sub fan-out of structured log frames."""

    def __init__(self, *, capacity: int = 500, subscriber_queue: int = 1_000) -> None:
        self._buffer: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._queue_size = subscriber_queue
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def publish(self, frame: dict[str, Any]) -> None:
        self._buffer.append(frame)
        if not self._subscribers:
            return
        loop = self._loop
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if loop is not None and running is not loop:
            # Called from a worker thread (asyncio.to_thread tools, uvicorn
            # internals) — hop onto the event loop thread.
            try:
                loop.call_soon_threadsafe(self._fan_out, frame)
            except RuntimeError:
                pass
            return
        self._fan_out(frame)

    def _fan_out(self, frame: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(frame)
            except asyncio.QueueFull:
                pass  # slow consumer — drop rather than block logging

    def recent(
        self, limit: int | None = None, *, min_level: str | None = None
    ) -> list[dict[str, Any]]:
        frames = [f for f in self._buffer if _passes(f, min_level)]
        return frames[-limit:] if limit else frames

    async def subscribe(self) -> AsyncIterator[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers.discard(queue)

    def frame_from_event(
        self, event_dict: dict[str, Any], *, logger_name: str | None
    ) -> dict[str, Any]:
        extra = {
            k: ("[redacted]" if _SENSITIVE.search(k) else _safe(v))
            for k, v in event_dict.items()
            if k not in _RESERVED
        }
        return {
            "timestamp": str(
                event_dict.get("timestamp")
                or dt.datetime.now(tz=dt.UTC).isoformat(timespec="milliseconds")
            ),
            "level": _normalize_level(event_dict.get("level") or event_dict.get("log_level")),
            "event": str(event_dict.get("event", ""))[:1_000],
            "request_id": event_dict.get("request_id"),
            "logger": logger_name or event_dict.get("logger"),
            "extra": extra,
        }


_LEVEL_ORDER = {"debug": 10, "info": 20, "warning": 30, "error": 40, "critical": 50}


def _passes(frame: dict[str, Any], min_level: str | None) -> bool:
    if not min_level:
        return True
    return _LEVEL_ORDER.get(frame["level"], 20) >= _LEVEL_ORDER.get(min_level, 0)


# A process-wide hub: logging is process-global, so is its broadcast.
_hub = LogHub()


def get_log_hub() -> LogHub:
    return _hub


def structlog_processor(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """structlog processor that mirrors each event into the hub."""
    try:
        frame = _hub.frame_from_event(
            {"level": method_name, **event_dict}, logger_name=event_dict.get("logger")
        )
        _hub.publish(frame)
    except Exception:  # logging must never raise
        pass
    return event_dict


class LogHubHandler(logging.Handler):
    """stdlib logging handler feeding the hub."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            from structlog.contextvars import get_contextvars

            context = get_contextvars()
        except Exception:
            context = {}
        try:
            event: dict[str, Any] = {
                "event": record.getMessage(),
                "level": record.levelname,
                "timestamp": dt.datetime.fromtimestamp(record.created, tz=dt.UTC).isoformat(
                    timespec="milliseconds"
                ),
                "request_id": context.get("request_id"),
            }
            if record.exc_info and record.exc_info[0] is not None:
                event["exc_type"] = record.exc_info[0].__name__
            _hub.publish(_hub.frame_from_event(event, logger_name=record.name))
        except Exception:
            self.handleError(record)


__all__ = ["LogHub", "LogHubHandler", "get_log_hub", "structlog_processor"]
