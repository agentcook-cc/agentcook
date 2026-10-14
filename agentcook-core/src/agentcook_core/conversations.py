"""Conversation transcripts — the short-term memory an agent loop needs.

A multi-turn agent must replay prior turns (including tool calls and
tool results) on every request. :class:`ConversationStoreProtocol` is the
persistence contract for that transcript; it is deliberately separate
from :class:`~agentcook_core.protocols.MemoryStoreProtocol` (long-term,
semantic, per-agent) because the access patterns differ: transcripts
are append-only, read in order, and owned by exactly one user.

:class:`InMemoryConversationStore` is the stdlib reference
implementation (tests, single-process dev, the teaching starter); the
PostgreSQL implementation lives in ``agentcook_storage``.

Ownership is enforced *in the store* rather than left to every caller:
:meth:`ConversationStoreProtocol.ensure_session` refuses to attach a user
to someone else's session, and reads return ``None`` / ``[]`` for
sessions the caller does not own, so existence never leaks.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Protocol, runtime_checkable

from agentcook_core.types import Message

MAX_TITLE_CHARS = 80


class SessionAccessError(PermissionError):
    """The session exists but belongs to a different user."""

    def __init__(self, session_id: str) -> None:
        super().__init__(f"session {session_id!r} belongs to another user")
        self.session_id = session_id


@dataclass(frozen=True, slots=True)
class ConversationSummary:
    """Listing metadata for one conversation."""

    session_id: str
    user_id: str
    agent: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0
    metadata: dict[str, object] = field(default_factory=dict)


def derive_title(text: str, *, limit: int = MAX_TITLE_CHARS) -> str:
    """First line of the first user message, trimmed for a sidebar."""
    line = " ".join(text.strip().split())
    if len(line) <= limit:
        return line or "New conversation"
    return line[: limit - 1].rstrip() + "…"


def _now() -> str:
    return dt.datetime.now(tz=dt.UTC).isoformat(timespec="milliseconds")


@runtime_checkable
class ConversationStoreProtocol(Protocol):
    """Persistence contract for conversation transcripts."""

    async def ensure_session(
        self,
        session_id: str,
        *,
        user_id: str,
        agent: str,
        title: str | None = None,
    ) -> ConversationSummary:
        """Return the session, creating it if missing.

        Raises :class:`SessionAccessError` if it belongs to another user.
        """
        ...

    async def get_session(self, session_id: str, *, user_id: str) -> ConversationSummary | None:
        """Session metadata, or ``None`` if missing / not owned by *user_id*."""
        ...

    async def append_messages(self, session_id: str, messages: Sequence[Message]) -> None:
        """Append messages (in order) to an existing session."""
        ...

    async def load_messages(
        self, session_id: str, *, user_id: str, limit: int | None = None
    ) -> list[Message]:
        """Oldest-first transcript; with ``limit`` only the newest *limit*."""
        ...

    async def list_sessions(self, user_id: str, *, limit: int = 50) -> list[ConversationSummary]:
        """The user's sessions, most recently updated first."""
        ...

    async def rename_session(
        self, session_id: str, *, user_id: str, title: str
    ) -> ConversationSummary | None:
        """Change the title; ``None`` if missing / not owned."""
        ...

    async def delete_session(self, session_id: str, *, user_id: str) -> bool:
        """Delete the session and its messages; ``False`` if missing / not owned."""
        ...


class InMemoryConversationStore:
    """Process-local :class:`ConversationStoreProtocol` implementation.

    Bounded by ``max_sessions`` (least-recently-updated sessions are
    evicted) so a long-running dev server cannot grow without limit.
    """

    def __init__(self, *, max_sessions: int = 10_000) -> None:
        self._sessions: dict[str, ConversationSummary] = {}
        self._messages: dict[str, list[Message]] = {}
        self._max_sessions = max_sessions
        self._lock = asyncio.Lock()

    def _owned(self, session_id: str, user_id: str) -> ConversationSummary | None:
        summary = self._sessions.get(session_id)
        if summary is None or summary.user_id != user_id:
            return None
        return summary

    async def ensure_session(
        self,
        session_id: str,
        *,
        user_id: str,
        agent: str,
        title: str | None = None,
    ) -> ConversationSummary:
        async with self._lock:
            existing = self._sessions.get(session_id)
            if existing is not None:
                if existing.user_id != user_id:
                    raise SessionAccessError(session_id)
                return existing
            now = _now()
            summary = ConversationSummary(
                session_id=session_id,
                user_id=user_id,
                agent=agent,
                title=derive_title(title or ""),
                created_at=now,
                updated_at=now,
            )
            self._sessions[session_id] = summary
            self._messages[session_id] = []
            if len(self._sessions) > self._max_sessions:
                oldest = min(self._sessions.values(), key=lambda s: s.updated_at)
                self._sessions.pop(oldest.session_id, None)
                self._messages.pop(oldest.session_id, None)
            return summary

    async def get_session(self, session_id: str, *, user_id: str) -> ConversationSummary | None:
        return self._owned(session_id, user_id)

    async def append_messages(self, session_id: str, messages: Sequence[Message]) -> None:
        async with self._lock:
            summary = self._sessions.get(session_id)
            if summary is None:
                raise KeyError(f"session {session_id!r} does not exist")
            stamped = [
                replace(
                    m, metadata={**m.metadata, "created_at": m.metadata.get("created_at", _now())}
                )
                for m in messages
            ]
            self._messages[session_id].extend(stamped)
            self._sessions[session_id] = replace(
                summary,
                updated_at=_now(),
                message_count=len(self._messages[session_id]),
            )

    async def load_messages(
        self, session_id: str, *, user_id: str, limit: int | None = None
    ) -> list[Message]:
        if self._owned(session_id, user_id) is None:
            return []
        messages = self._messages.get(session_id, [])
        return list(messages[-limit:] if limit else messages)

    async def list_sessions(self, user_id: str, *, limit: int = 50) -> list[ConversationSummary]:
        owned = [s for s in self._sessions.values() if s.user_id == user_id]
        owned.sort(key=lambda s: s.updated_at, reverse=True)
        return owned[:limit]

    async def rename_session(
        self, session_id: str, *, user_id: str, title: str
    ) -> ConversationSummary | None:
        async with self._lock:
            summary = self._owned(session_id, user_id)
            if summary is None:
                return None
            updated = replace(summary, title=derive_title(title), updated_at=_now())
            self._sessions[session_id] = updated
            return updated

    async def delete_session(self, session_id: str, *, user_id: str) -> bool:
        async with self._lock:
            if self._owned(session_id, user_id) is None:
                return False
            self._sessions.pop(session_id, None)
            self._messages.pop(session_id, None)
            return True


__all__ = [
    "ConversationStoreProtocol",
    "ConversationSummary",
    "InMemoryConversationStore",
    "SessionAccessError",
    "derive_title",
]
