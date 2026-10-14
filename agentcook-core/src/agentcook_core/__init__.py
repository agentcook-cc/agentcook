"""agentcook-core: engine-agnostic agent harness.

Contracts (structural protocols + value types) used by every downstream
agentcook package, plus the zero-dependency runtime built on them:

- :mod:`agentcook_core.agent`  — the agent loop (``Agent`` / ``AgentRunner``)
- :mod:`agentcook_core.tools`  — ``@tool`` decorator, ``Toolset``, ``RunContext``
- :mod:`agentcook_core.prompts` — cache-friendly system-prompt assembly
- :mod:`agentcook_core.builtin_tools` — time / calculator / load_skill

It has no runtime dependencies on specific orchestration engines, LLM
providers, or storage backends.
"""

from __future__ import annotations

from agentcook_core.agent import (
    Agent,
    AgentEvent,
    AgentRunError,
    AgentRunner,
    AgentTool,
    CompositeHooks,
    ContextWindow,
    RunCompleted,
    RunFailed,
    RunHooks,
    RunStarted,
    TextDelta,
    ToolCallCompleted,
    ToolCallStarted,
    ToolDecision,
    ToolPolicy,
    TurnCompleted,
)
from agentcook_core.protocols import (
    AgentProtocol,
    ConnectorProtocol,
    IdentityProtocol,
    LLMProviderProtocol,
    MemoryStoreProtocol,
    PluginProtocol,
    SkillProtocol,
    SoulProtocol,
    ToolProtocol,
)
from agentcook_core.tools import (
    FunctionTool,
    RunContext,
    ToolInputError,
    Toolset,
    current_run_context,
    tool,
)
from agentcook_core.types import (
    AgentResponse,
    ChatChunk,
    ChatResponse,
    ConnectorConfig,
    ConnectorKind,
    FinishReason,
    IdentityCard,
    MemoryEvent,
    MemoryEventKind,
    MemoryHit,
    MemoryRecall,
    Message,
    ModelSpec,
    PluginManifest,
    Role,
    SkillManifest,
    SoulConfig,
    TokenUsage,
    ToolCall,
    ToolResult,
)

__version__ = "0.2.0"

__all__ = [
    "Agent",
    "AgentEvent",
    "AgentProtocol",
    "AgentRunError",
    "AgentRunner",
    "AgentTool",
    "CompositeHooks",
    "ContextWindow",
    "FunctionTool",
    "RunCompleted",
    "RunContext",
    "RunFailed",
    "RunHooks",
    "RunStarted",
    "TextDelta",
    "ToolCallCompleted",
    "ToolCallStarted",
    "ToolDecision",
    "ToolInputError",
    "ToolPolicy",
    "Toolset",
    "TurnCompleted",
    "current_run_context",
    "tool",
    "AgentResponse",
    "ChatChunk",
    "ChatResponse",
    "ConnectorConfig",
    "ConnectorKind",
    "ConnectorProtocol",
    "FinishReason",
    "IdentityCard",
    "IdentityProtocol",
    "LLMProviderProtocol",
    "MemoryEvent",
    "MemoryEventKind",
    "MemoryHit",
    "MemoryRecall",
    "MemoryStoreProtocol",
    "Message",
    "ModelSpec",
    "PluginManifest",
    "PluginProtocol",
    "Role",
    "SkillManifest",
    "SkillProtocol",
    "SoulConfig",
    "SoulProtocol",
    "TokenUsage",
    "ToolCall",
    "ToolProtocol",
    "ToolResult",
    "__version__",
]
