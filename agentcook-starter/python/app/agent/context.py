"""Conversation memory: what the LLM sees on every call.

Each session keeps its messages in Anthropic Messages API format:
  {"role": "user", "content": "..."}                      user text
  {"role": "assistant", "content": [text/tool_use blocks]}  model output
  {"role": "user", "content": [tool_result blocks]}       tool results
"""

import asyncio
from collections import OrderedDict


def _is_user_text(message: dict) -> bool:
    return message["role"] == "user" and isinstance(message["content"], str)


class ContextManager:
    def __init__(self, session_id: str, max_messages: int = 20):
        self.session_id = session_id
        self.max_messages = max(max_messages, 2)
        self._messages: list[dict] = []
        self.lock = asyncio.Lock()  # one reply at a time per conversation

    def add_user_message(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})
        self._trim()

    def add_assistant_message(self, content: str | list[dict]) -> None:
        self._messages.append({"role": "assistant", "content": content})

    def add_tool_results(self, results: list[dict]) -> None:
        """``results`` are ``tool_result`` blocks, one per ``tool_use`` in the previous message."""
        self._messages.append({"role": "user", "content": results})

    def get_messages(self) -> list[dict]:
        return list(self._messages)

    def __len__(self) -> int:
        return len(self._messages)

    # A failed turn must not leave half a turn behind (e.g. a tool_use with
    # no tool_result — the API rejects the whole history after that).
    def checkpoint(self) -> list[dict]:
        return list(self._messages)

    def rollback(self, snapshot: list[dict]) -> None:
        self._messages = list(snapshot)

    def _trim(self) -> None:
        """Keep the first message (the original ask) + the most recent ones.

        Only called when a new user message arrives, so a turn in progress is
        never cut. The kept tail must start at a plain user message: starting
        at a tool_result would orphan it from its tool_use, which the API
        rejects.
        """
        if len(self._messages) <= self.max_messages:
            return
        tail = self._messages[-(self.max_messages - 1) :]
        while not _is_user_text(tail[0]):
            tail = tail[1:]  # the newest message is user text, so this stops
        self._messages = self._messages[:1] + tail


class SessionStore:
    """In-memory sessions, least recently used dropped first. Swap for Redis/DB in production."""

    def __init__(self, max_sessions: int = 1000, max_messages: int = 20):
        self.max_sessions = max_sessions
        self.max_messages = max_messages
        self._sessions: OrderedDict[str, ContextManager] = OrderedDict()

    def get(self, session_id: str) -> ContextManager:
        context = self._sessions.get(session_id)
        if context is None:
            context = self._sessions[session_id] = ContextManager(session_id, self.max_messages)
        self._sessions.move_to_end(session_id)
        while len(self._sessions) > self.max_sessions:
            self._sessions.popitem(last=False)
        return context

    def delete(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None
