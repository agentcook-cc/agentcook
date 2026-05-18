"""agentcook-core: engine-agnostic Agent / Skill / Plugin / Connector / Tool contracts.

This package defines the 5 structural protocols and value types used by
every downstream agentcook package. It has no runtime dependencies on
specific orchestration engines, LLM providers, or storage backends.
"""

from __future__ import annotations

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

__version__ = "0.1.0"

__all__ = [
    "AgentProtocol",
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
