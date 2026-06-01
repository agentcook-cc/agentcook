"""Value types shared across all agentcook protocols.

Pure dataclasses with no behavior. Engine-agnostic — these types must
not import or depend on any specific Agent runtime (no google-adk,
LangChain, LangGraph, etc.). Engine integrations live in downstream
packages and adapt to these types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A single tool invocation requested by an assistant message.

    Mirrors OpenAI ChatML's ``tool_calls`` element. ``arguments`` is the
    parsed JSON object — providers serialize/deserialize the wire form.
    """

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Message:
    """A single turn in an agent conversation.

    Field semantics by ``role``:

    - ``system`` / ``user``     — ``content`` carries the text; ``name``
      may identify the participant (rare).
    - ``assistant``             — ``content`` is the model's reply text
      (may be empty when only emitting tool calls); ``tool_calls`` lists
      requested invocations.
    - ``tool``                  — ``content`` is the tool's result text;
      ``tool_call_id`` binds back to the assistant turn that requested
      it; ``name`` SHOULD echo the tool name.
    """

    role: Role
    content: str
    name: str | None = None
    tool_calls: tuple[ToolCall, ...] | None = None
    tool_call_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Provider-qualified model identifier (mirrors agent.schema.json `model`)."""

    provider: str
    name: str


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token accounting for a single agent invocation."""

    input: int = 0
    output: int = 0
    cached: int = 0

    @property
    def total(self) -> int:
        return self.input + self.output


FinishReason = Literal["stop", "length", "tool_calls", "content_filter", "error"]


@dataclass(frozen=True, slots=True)
class AgentResponse:
    """Result returned by `AgentProtocol.run`.

    An agent turn may invoke the LLM multiple times (tool loops); the
    accumulated `usage` reports the total. Use `ChatResponse` for the
    *single* LLM call.
    """

    output: str
    messages: list[Message] = field(default_factory=list)
    usage: TokenUsage = field(default_factory=TokenUsage)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ChatResponse:
    """Result of a single LLM ``chat`` call (one round-trip).

    Distinct from :class:`AgentResponse`: an Agent.run() may issue many
    LLM chats. Use this type for the provider-level contract.
    """

    message: Message
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: FinishReason | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ChatChunk:
    """One streamed delta from an LLM ``stream_chat`` call.

    Empty ``delta_content`` is valid (e.g. when only emitting tool-call
    fragments). ``finish_reason`` is set on the terminal chunk.
    """

    delta_content: str = ""
    delta_tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: FinishReason | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Result returned by `ToolProtocol.invoke`."""

    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ConnectorKind(str, Enum):
    """Connector flavors supported by the plugin spec.

    ``WEBHOOK`` is required for IM event-callback integrations (e.g. DingTalk
    / Lark message events). gRPC is intentionally absent — that flavor is a
    swarm-internal transport detail and does not belong in the public
    plugin/connector surface.
    """

    MCP = "mcp"
    OAUTH = "oauth"
    HTTP = "http"
    CUSTOM = "custom"
    WEBHOOK = "webhook"


@dataclass(frozen=True, slots=True)
class ConnectorConfig:
    """Declarative connector binding (mirrors connectors.schema.json entries)."""

    name: str
    kind: ConnectorKind
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SkillManifest:
    """Skill metadata read from a skill bundle's frontmatter."""

    name: str
    description: str
    version: str = "0.0.0"


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """Plugin manifest (mirrors plugin.schema.json required fields)."""

    name: str
    display_name: str
    version: str
    description: str
    author: str | None = None
    category: str | None = None
    default_agent: str | None = None


# --------------------------------------------------------------------------
# Memory / Identity / Soul value types (ADR-011)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IdentityCard:
    """Immutable identity record for an Agent.

    Per ADR-011 the Identity layer is locked at creation — the only way to
    "edit" Identity is to delete the Agent and create a new one. Mutating
    methods are intentionally absent; ``frozen=True`` is the enforcement.
    """

    name: str
    role: str
    created_at: str  # ISO-8601 UTC; storage layer is responsible for parsing
    scopes: frozenset[str] = field(default_factory=frozenset)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SoulConfig:
    """Agent personality configuration — stable but user-adjustable.

    ``SoulConfig`` is frozen; persistent updates are performed by writing a
    new instance through the storage layer. This makes Soul changes
    auditable (each version is a distinct value) and prevents in-place
    drift across concurrent Agent invocations.
    """

    tone: str = "neutral"
    language_style: str = "concise"
    values: tuple[str, ...] = ()
    custom_traits: dict[str, str] = field(default_factory=dict)


MemoryEventKind = Literal["observation", "decision", "tool_use", "user_input", "reflection"]


@dataclass(frozen=True, slots=True)
class MemoryEvent:
    """A single entry in the long-term event stream."""

    timestamp: str  # ISO-8601 UTC
    kind: MemoryEventKind
    content: str
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryHit:
    """One result returned from a semantic-recall query.

    ``score`` is provider-defined (typically a normalized relevance in
    ``[0, 1]``). The hybrid retriever (BM25 + embedding, see ADR-011) is
    expected to fuse component scores before returning.
    """

    content: str
    score: float
    event: MemoryEvent | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryRecall:
    """A semantic-recall query result set."""

    query: str
    hits: tuple[MemoryHit, ...] = ()


__all__ = [
    "AgentResponse",
    "ChatChunk",
    "ChatResponse",
    "ConnectorConfig",
    "ConnectorKind",
    "FinishReason",
    "IdentityCard",
    "MemoryEvent",
    "MemoryEventKind",
    "MemoryHit",
    "MemoryRecall",
    "Message",
    "ModelSpec",
    "PluginManifest",
    "Role",
    "SkillManifest",
    "SoulConfig",
    "TokenUsage",
    "ToolCall",
    "ToolResult",
]
