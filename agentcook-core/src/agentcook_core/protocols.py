"""Core protocols defining the agentcook plugin & runtime surface.

Structural protocols form the contract between agentcook-core and every
downstream package (providers, storage, sandboxed plugins, swarm
services, third-party extensions):

- :class:`AgentProtocol`        — an addressable conversation participant.
- :class:`SkillProtocol`        — a reusable instruction bundle ("work manual").
- :class:`PluginProtocol`       — a packaged agents + skills + connectors set.
- :class:`ConnectorProtocol`    — a declarative binding to an external service.
- :class:`ToolProtocol`         — a callable function exposed to an Agent.
- :class:`LLMProviderProtocol`  — a single-round LLM transport (OpenAI / Anthropic / …).
- :class:`IdentityProtocol`     — an Agent's immutable identity card (ADR-011).
- :class:`SoulProtocol`         — an Agent's stable-but-adjustable personality (ADR-011).
- :class:`MemoryStoreProtocol`  — short-term KV + long-term events + semantic recall (ADR-011).

All protocols are :func:`runtime_checkable` so adapters can be validated at
plugin load time. Field shapes mirror the public ``plugin.schema.json`` /
``agent.schema.json`` / ``connectors.schema.json`` already published in
``agent-plugin-spec`` so downstream tooling can cross-validate.

Design choices (see ADR-001 / ADR-002):
- Async-first: any I/O bound method is ``async``. Sync wrappers are an
  adapter concern, not a core concern.
- No engine lock-in: nothing here imports a specific orchestration engine.
  ``LangGraph`` / ``google-adk`` integrations live in downstream packages
  and adapt to these protocols.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any, Protocol, runtime_checkable

from agentcook_core.types import (
    AgentResponse,
    ChatChunk,
    ChatResponse,
    ConnectorConfig,
    IdentityCard,
    MemoryEvent,
    MemoryRecall,
    Message,
    ModelSpec,
    PluginManifest,
    SkillManifest,
    SoulConfig,
    ToolResult,
)


@runtime_checkable
class ToolProtocol(Protocol):
    """A callable function an Agent can invoke.

    Tools are the smallest unit of side-effecting execution. Each Tool
    exposes a JSON-schema parameter spec so the LLM Function Calling
    layer (providers package) can wire it without runtime introspection.
    """

    @property
    def name(self) -> str:
        """Stable identifier used in function-call payloads."""

    @property
    def description(self) -> str:
        """Human-readable summary shown to the LLM."""

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """JSON Schema draft-07 object describing accepted arguments."""

    async def invoke(self, arguments: dict[str, Any]) -> ToolResult:
        """Execute the tool. Must not raise on user-facing errors; return
        a :class:`ToolResult` with ``success=False`` instead."""


@runtime_checkable
class SkillProtocol(Protocol):
    """A reusable instruction bundle.

    A Skill is markdown + optional resources that teaches an Agent *how*
    to perform a task. It carries no executable code (executable behavior
    lives behind Tools / Connectors). Skills are loaded lazily by
    ``skill_loader`` and may be platform-shared or plugin-private.
    """

    @property
    def manifest(self) -> SkillManifest:
        """Skill metadata parsed from frontmatter."""

    def load(self) -> str:
        """Return the rendered instruction body (markdown).

        Synchronous — Skills are filesystem reads only. Loading is
        expected to be cached by the loader, so implementations should
        not memoize internally.
        """


@runtime_checkable
class ConnectorProtocol(Protocol):
    """A declarative binding to an external service.

    Connector instances are created from :class:`ConnectorConfig`
    declarations in ``connectors/connectors.json`` and brokered by the
    runtime. Concrete implementations (MCP, OAuth, custom) live in the
    ``connector`` package; this protocol fixes only the lifecycle shape.
    """

    @property
    def config(self) -> ConnectorConfig:
        """The declarative config this connector was built from."""

    async def open(self) -> None:
        """Establish the connection / OAuth session / MCP handshake."""

    async def close(self) -> None:
        """Release resources. Safe to call on a never-opened connector."""

    async def tools(self) -> Sequence[ToolProtocol]:
        """Tools exposed by this connector (e.g. MCP server tools)."""


@runtime_checkable
class AgentProtocol(Protocol):
    """An addressable conversation participant.

    Agents own a model selection + tool/skill set and respond to a
    sequence of messages. Multi-agent orchestration (delegation,
    routing) is built on top via LangGraph adapters (see ADR-002) and is
    *not* part of the core Agent contract.
    """

    @property
    def name(self) -> str:
        """Display name (matches ``agent.json.name``)."""

    @property
    def description(self) -> str:
        """Purpose statement used for delegation routing."""

    @property
    def model(self) -> ModelSpec:
        """Provider + model name the Agent is configured against."""

    async def run(
        self,
        messages: Sequence[Message],
        *,
        context: dict[str, Any] | None = None,
    ) -> AgentResponse:
        """Execute one agent turn against the given message history."""


@runtime_checkable
class PluginProtocol(Protocol):
    """A packaged Agent + Skill + Connector bundle.

    A Plugin is the deployable unit recognized by the platform. Its
    on-disk layout is the published ``agent-plugin-spec`` schema; this
    protocol is the in-memory handle the runtime gets back after
    ``plugin_loader`` parses the bundle.
    """

    @property
    def manifest(self) -> PluginManifest:
        """Manifest parsed from ``plugin.json``."""

    @property
    def agents(self) -> Sequence[AgentProtocol]:
        """Agents declared under ``agents/``."""

    @property
    def skills(self) -> Sequence[SkillProtocol]:
        """Skills declared under ``skills/``."""

    @property
    def connectors(self) -> Sequence[ConnectorProtocol]:
        """Connectors declared in ``connectors/connectors.json``."""

    async def activate(self) -> None:
        """Called once when the runtime mounts the plugin."""

    async def deactivate(self) -> None:
        """Called when the runtime unmounts the plugin (hot reload, etc.)."""


@runtime_checkable
class LLMProviderProtocol(Protocol):
    """Single-round LLM transport — one ``chat`` call, one response.

    A *provider* in agentcook is a thin async adapter around a vendor SDK
    (``openai`` / ``anthropic`` / ``zai-sdk`` / Qwen via OpenAI-compatible
    endpoint). It does not own conversation state or tool loops — those
    live in the Agent layer. Composition of multiple providers (fallback,
    routing) is implemented in ``agentcook_providers`` and itself
    satisfies this protocol.
    """

    @property
    def model_name(self) -> str:
        """Vendor-qualified model identifier (e.g. ``gpt-4o``)."""

    @property
    def context_window(self) -> int:
        """Maximum input window in tokens; consumed by compaction logic."""

    async def chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolProtocol] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        """Issue one synchronous LLM round-trip and return the result."""

    def stream_chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolProtocol] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """Issue a streaming LLM call and yield deltas as they arrive.

        Note: this is *not* declared ``async`` — it is an async-generator
        factory. Implementations write ``async def stream_chat(...)`` with
        ``yield``; the function-level type stays ``AsyncIterator``.
        """

    def count_tokens(self, text: str) -> int:
        """Approximate the token count for *text* under this model.

        Implementations may use vendor-specific tokenizers (tiktoken for
        OpenAI, etc.) or a character-heuristic fallback.
        """


@runtime_checkable
class IdentityProtocol(Protocol):
    """An Agent's immutable identity card (ADR-011 Layer 1).

    Implementations must expose ``card`` returning an :class:`IdentityCard`
    that does not change over the lifetime of the Agent. Mutation is
    expressed at the storage layer by creating a *new* Agent — there is
    deliberately no ``update_identity`` method on the protocol surface.
    """

    @property
    def card(self) -> IdentityCard:
        """Return the immutable identity record."""


@runtime_checkable
class SoulProtocol(Protocol):
    """An Agent's stable-but-adjustable personality (ADR-011 Layer 2).

    Soul is conceptually mutable but operationally append-only: each
    ``replace`` produces a new :class:`SoulConfig` value which the storage
    layer versions. This keeps personality drift auditable.
    """

    @property
    def config(self) -> SoulConfig:
        """Current personality configuration."""

    async def replace(self, config: SoulConfig) -> SoulConfig:
        """Replace the personality config; return the persisted version."""


@runtime_checkable
class MemoryStoreProtocol(Protocol):
    """Agent memory backplane (ADR-011 Layer 3 — short / long / semantic).

    The three tiers are intentionally exposed as separate method groups so
    callers can be explicit about which kind of memory they're touching:

    - **session KV** — per-conversation working memory; ephemeral, TTLed.
    - **event stream** — append-only durable record of agent activity;
      drives long-term reflection and audit.
    - **semantic recall** — hybrid (BM25 + embedding, see ADR-011)
      retrieval over the event stream + arbitrary indexed content.

    Concrete implementations live in ``agentcook_storage``. Auto Dream
    (background reflection) is *not* part of this protocol — it belongs
    to a higher orchestration layer (default-off per ADR-011).
    """

    # --- session KV ----------------------------------------------------
    async def remember_session(
        self,
        session_id: str,
        key: str,
        value: Any,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        """Write to per-session working memory; ``ttl_seconds`` opt-in."""

    async def recall_session(self, session_id: str, key: str) -> Any | None:
        """Read from per-session working memory; ``None`` if absent/expired."""

    # --- event stream --------------------------------------------------
    async def append_event(self, agent_id: str, event: MemoryEvent) -> None:
        """Append-only write to the long-term event stream."""

    async def stream_events(
        self,
        agent_id: str,
        *,
        since: str | None = None,
        kind: str | None = None,
        limit: int = 100,
    ) -> Sequence[MemoryEvent]:
        """Read recent events; oldest-first within the window."""

    # --- semantic recall ----------------------------------------------
    async def search(
        self,
        agent_id: str,
        query: str,
        *,
        top_k: int = 5,
    ) -> MemoryRecall:
        """Hybrid (BM25 + embedding) retrieval over the agent's memory."""


__all__ = [
    "AgentProtocol",
    "ConnectorProtocol",
    "IdentityProtocol",
    "LLMProviderProtocol",
    "MemoryStoreProtocol",
    "PluginProtocol",
    "SkillProtocol",
    "SoulProtocol",
    "ToolProtocol",
]
