"""Echo provider — minimal teaching stub satisfying ``LLMProviderProtocol``.

Has no external dependencies; doubles as a fixture for FallbackProvider
unit tests so they don't need to mock the real OpenAI client.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from agentcook_core import (
    ChatChunk,
    ChatResponse,
    Message,
    TokenUsage,
    ToolProtocol,
)


class EchoProvider:
    """A toy LLM provider that echoes the latest user message."""

    def __init__(self, prefix: str = "Echo", model: str = "echo-v0") -> None:
        self._prefix = prefix
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def context_window(self) -> int:
        return 8_192

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def _last_user(self, messages: Sequence[Message]) -> str:
        for msg in reversed(messages):
            if msg.role == "user":
                return msg.content
        return ""

    async def chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolProtocol] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        text = f"[{self._prefix}] {self._last_user(messages)}"
        return ChatResponse(
            message=Message(role="assistant", content=text),
            usage=TokenUsage(input=self.count_tokens(self._last_user(messages)), output=self.count_tokens(text)),
            finish_reason="stop",
        )

    async def stream_chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolProtocol] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        text = f"[{self._prefix}] {self._last_user(messages)}"
        for ch in text:
            yield ChatChunk(delta_content=ch)
        yield ChatChunk(delta_content="", finish_reason="stop")


__all__ = ["EchoProvider"]
