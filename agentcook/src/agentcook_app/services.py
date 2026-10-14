"""Agent runtime business layer — sits between routers and storage.

For Day 13 we ship a single in-memory implementation, ``InMemoryAgentRuntime``,
so the FastAPI surface can land + be covered by unit tests without a live
PostgreSQL. The real ``PgRuntime`` (wrapping ``PgVectorMemoryStore`` + a
``SoulRepository`` over asyncpg) lands Phase 2 Day 17 when embedding
providers come online — the public method set on this module is the contract
both implementations must honour.

The service exposes a duck-typed interface; routers depend on
``AgentRuntime`` by type hint and ``Depends(get_runtime)`` for injection.
Tests swap implementations through ``app.dependency_overrides``.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from agentcook_core import (
    IdentityCard,
    MemoryEvent,
    MemoryHit,
    MemoryRecall,
    SoulConfig,
)
from fastapi import Request

# --------------------------------------------------------------------------
# Errors — routers map these to HTTP via the exception handler in errors.py
# --------------------------------------------------------------------------


class AgentNotFoundError(LookupError):
    """The requested agent_id is not registered."""

    def __init__(self, agent_id: str) -> None:
        super().__init__(f"Agent {agent_id!r} not found")
        self.agent_id = agent_id


class SoulNotInitializedError(LookupError):
    """The agent exists but has no soul versions yet."""

    def __init__(self, agent_id: str) -> None:
        super().__init__(f"Agent {agent_id!r} has no SoulConfig yet")
        self.agent_id = agent_id


# --------------------------------------------------------------------------
# Value types specific to the service layer
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SoulVersion:
    """A single point in the per-agent soul history."""

    version: int
    created_at: str
    config: SoulConfig


@dataclass(frozen=True, slots=True)
class StoredMemoryEvent:
    """A :class:`MemoryEvent` paired with its server-assigned id."""

    id: str
    event: MemoryEvent


@dataclass(frozen=True, slots=True)
class FlushResult:
    deleted_event_count: int
    identity_preserved: bool
    soul_preserved: bool


# --------------------------------------------------------------------------
# Service protocol (Day 17 PgRuntime will satisfy it too)
# --------------------------------------------------------------------------


@runtime_checkable
class AgentRuntime(Protocol):
    async def ensure_agent(
        self, agent_id: str, card: IdentityCard, *, user_id: str
    ) -> IdentityCard: ...
    async def get_owner(self, agent_id: str) -> str | None: ...
    async def get_identity(self, agent_id: str) -> IdentityCard: ...
    async def get_soul_latest(self, agent_id: str) -> SoulVersion: ...
    async def append_soul(self, agent_id: str, config: SoulConfig) -> SoulVersion: ...
    async def list_soul_history(
        self, agent_id: str, *, limit: int = 50
    ) -> Sequence[SoulVersion]: ...
    async def append_memory_event(self, agent_id: str, event: MemoryEvent) -> StoredMemoryEvent: ...
    async def list_memory_events(
        self,
        agent_id: str,
        *,
        since: str | None = None,
        kind: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[Sequence[StoredMemoryEvent], str | None]: ...
    async def search_memory(self, agent_id: str, query: str, *, top_k: int = 5) -> MemoryRecall: ...
    async def flush_memory(
        self, agent_id: str, *, preserve_identity_and_soul: bool = True
    ) -> FlushResult: ...


# --------------------------------------------------------------------------
# In-memory implementation
# --------------------------------------------------------------------------


def _now_iso() -> str:
    return dt.datetime.now(tz=dt.UTC).isoformat(timespec="seconds")


_RECALL_STOPWORDS = frozenset(
    "a an and are do does for i is it me my of on or the to what which who you your".split()
)


def _recall_terms(text: str) -> set[str]:
    words = {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _RECALL_STOPWORDS}
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        words.update(run[i : i + 2] for i in range(max(1, len(run) - 1)))
    return {w for w in words if len(w) > 1 or w.isdigit() or not w.isascii()}


class InMemoryAgentRuntime:
    """Process-local runtime used in tests + Day 13 dev.

    Identity is registered via :meth:`seed_agent` (or :meth:`create_agent`
    for tests that want to exercise creation). Per ADR-011 the
    identity card is immutable once registered.
    """

    def __init__(self) -> None:
        self._agents: dict[str, IdentityCard] = {}
        self._souls: dict[str, list[SoulVersion]] = {}
        self._events: dict[str, list[StoredMemoryEvent]] = {}
        self._event_seq: dict[str, int] = {}
        self._owners: dict[str, str] = {}

    # ---- test helpers ------------------------------------------------

    def seed_agent(self, card: IdentityCard, *, agent_id: str | None = None) -> str:
        aid = agent_id or card.name
        if aid in self._agents:
            raise ValueError(f"Agent {aid!r} already exists")
        self._agents[aid] = card
        return aid

    # ---- protocol implementation -------------------------------------

    async def ensure_agent(
        self, agent_id: str, card: IdentityCard, *, user_id: str
    ) -> IdentityCard:
        """Create the agent instance on first use; return the stored card.

        Identity is immutable (ADR-011): an existing card is returned
        unchanged even if *card* differs.
        """
        existing = self._agents.get(agent_id)
        if existing is not None:
            return existing
        self._agents[agent_id] = card
        self._owners[agent_id] = user_id
        return card

    async def get_owner(self, agent_id: str) -> str | None:
        return self._owners.get(agent_id)

    def _require(self, agent_id: str) -> IdentityCard:
        if agent_id not in self._agents:
            raise AgentNotFoundError(agent_id)
        return self._agents[agent_id]

    async def get_identity(self, agent_id: str) -> IdentityCard:
        return self._require(agent_id)

    async def get_soul_latest(self, agent_id: str) -> SoulVersion:
        self._require(agent_id)
        versions = self._souls.get(agent_id)
        if not versions:
            raise SoulNotInitializedError(agent_id)
        return versions[-1]

    async def append_soul(self, agent_id: str, config: SoulConfig) -> SoulVersion:
        self._require(agent_id)
        history = self._souls.setdefault(agent_id, [])
        version = SoulVersion(
            version=len(history) + 1,
            created_at=_now_iso(),
            config=config,
        )
        history.append(version)
        return version

    async def list_soul_history(self, agent_id: str, *, limit: int = 50) -> Sequence[SoulVersion]:
        self._require(agent_id)
        history = self._souls.get(agent_id, [])
        return tuple(history[-limit:])

    async def append_memory_event(self, agent_id: str, event: MemoryEvent) -> StoredMemoryEvent:
        self._require(agent_id)
        seq = self._event_seq.get(agent_id, 0) + 1
        self._event_seq[agent_id] = seq
        stored = StoredMemoryEvent(id=f"evt_{seq}", event=event)
        self._events.setdefault(agent_id, []).append(stored)
        return stored

    async def list_memory_events(
        self,
        agent_id: str,
        *,
        since: str | None = None,
        kind: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[Sequence[StoredMemoryEvent], str | None]:
        self._require(agent_id)
        items: list[StoredMemoryEvent] = list(self._events.get(agent_id, []))
        if since is not None:
            items = [s for s in items if s.event.timestamp >= since]
        if kind is not None:
            items = [s for s in items if s.event.kind == kind]
        if cursor is not None:
            for idx, stored in enumerate(items):
                if stored.id == cursor:
                    items = items[idx + 1 :]
                    break
            else:
                items = []
        page = items[:limit]
        next_cursor = page[-1].id if len(items) > limit else None
        return tuple(page), next_cursor

    async def search_memory(self, agent_id: str, query: str, *, top_k: int = 5) -> MemoryRecall:
        """Keyword-overlap recall (the dev stand-in for pgvector search).

        Scores each event by the fraction of query terms it contains, so
        "what tone do I prefer" finds "User prefers a friendly tone" — a
        plain substring test would miss it.
        """
        self._require(agent_id)
        terms = _recall_terms(query)
        if not terms:
            return MemoryRecall(query=query, hits=())
        needle = query.strip().lower()
        scored: list[tuple[float, StoredMemoryEvent]] = []
        for stored in self._events.get(agent_id, []):
            if needle and needle in stored.event.content.lower():
                scored.append((1.0, stored))  # verbatim phrase match ranks first
                continue
            overlap = len(terms & _recall_terms(stored.event.content))
            if overlap:
                scored.append((0.9 * overlap / len(terms), stored))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        hits = tuple(
            MemoryHit(
                content=stored.event.content,
                score=round(score, 4),
                event=stored.event,
                metadata={"id": stored.id},
            )
            for score, stored in scored[:top_k]
        )
        return MemoryRecall(query=query, hits=hits)

    async def flush_memory(
        self, agent_id: str, *, preserve_identity_and_soul: bool = True
    ) -> FlushResult:
        self._require(agent_id)
        count = len(self._events.pop(agent_id, []))
        self._event_seq.pop(agent_id, None)
        if not preserve_identity_and_soul:
            self._souls.pop(agent_id, None)
        # Identity remains either way (it's immutable; full removal is "delete agent",
        # a Java responsibility per ADR-013).
        return FlushResult(
            deleted_event_count=count,
            identity_preserved=True,
            soul_preserved=preserve_identity_and_soul,
        )


# --------------------------------------------------------------------------
# Dependency wiring (router → service)
# --------------------------------------------------------------------------


def get_runtime(request: Request) -> AgentRuntime:
    """FastAPI dependency → the app container's runtime.

    Tests override it via ``app.dependency_overrides[get_runtime]``.
    """
    return request.app.state.container.runtime


__all__ = [
    "AgentNotFoundError",
    "AgentRuntime",
    "FlushResult",
    "InMemoryAgentRuntime",
    "SoulNotInitializedError",
    "SoulVersion",
    "StoredMemoryEvent",
    "get_runtime",
]
