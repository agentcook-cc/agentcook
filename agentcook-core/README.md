# agentcook-core

Engine-agnostic Agent / Skill / Plugin / Connector / Tool contracts and runtime modules.

Zero third-party dependencies (stdlib-only). All extension points use `typing.Protocol` for dependency inversion — concrete implementations (LLM providers, storage backends, Docker SDK) live in downstream packages.

## Install

```bash
pip install agentcook-core
```

## Modules

| Module | Purpose | Key Types |
|--------|---------|-----------|
| `protocols` | 9 structural protocols (Agent, Skill, Plugin, Connector, Tool, LLMProvider, Identity, Soul, MemoryStore) | `AgentProtocol`, `ToolProtocol`, `LLMProviderProtocol` |
| `types` | Frozen dataclasses shared across all protocols | `Message`, `ModelSpec`, `ChatResponse`, `MemoryEvent` |
| `skill_loader` | Frontmatter-based skill bundle parser + registry | `SkillEntry`, `SkillRegistry` |
| `plugin_loader` | Plugin bundle loader + sandbox integration | `PluginEntry`, `PluginRegistry`, `SandboxRunner` Protocol |
| `connector` | 4-adapter connector framework (OAuth/HTTP/MCP/Webhook) | `ConnectorManager`, `OAuthAdapter`, `HttpAdapter` |
| `multi_agent` | Declarative router config → StateGraph compilation | `RouterConfig`, `MultiAgentOrchestrator`, `GraphCompiler` Protocol |
| `mcp_adapter` | MCP protocol client + Tool adapter | `McpClient`, `McpToolAdapter`, `McpToolRegistry` |
| `model_router` | Cost/quality/fallback model selection | `ModelConfig`, `ModelRouter`, `RoutingPolicy` |
| `hook_runtime` | Pre/post hook pipeline (onion model) | `Hook` Protocol, `HookPipeline`, `HookRegistry` |
| `memory` | Four-layer memory (Identity/Soul/Memory/Diary) | `MemoryManager`, `MemoryStore` Protocol, `SoulManager` |
| `sandbox_runner` | Docker sandbox executor for plugins | `SandboxExecutor` Protocol, `DockerSandboxExecutor`, `SandboxConfig` |
| `media` | Rich media processing + renderer pipeline | `MediaType`, `MediaAttachment`, `MediaProcessor` Protocol, `MediaRegistry` |
| `compaction` | Context compaction + token budget pruning | `CompactionStrategy`, `SlidingWindowCompaction`, `TokenBudgetPruning`, `MemorySummarizer` |
| `tracing` | OTel-shaped tracer/span Protocol with NoOp default; runtime injects a real adapter | `Tracer` / `Span` Protocol, `NoOpTracer`, `set_tracer` / `get_tracer` |
| `langfuse_hook` | LLM observability hook (model call observation) with NoOp default | `LangfuseHook` Protocol, `NoOpHook`, `set_langfuse_hook` / `get_langfuse_hook` |

## Quick Start

```python
from agentcook_core import AgentProtocol, ToolProtocol, Message, ModelSpec
from agentcook_core.model_router import ModelConfig, ModelRouter, ModelRegistry, RoutingPolicy
from agentcook_core.hook_runtime import HookPipeline, HookRegistry, HookEvent, LoggingHook
from agentcook_core.memory import MemoryManager, InMemoryStore, MemoryLayer

# Model routing
registry = ModelRegistry()
registry.register(ModelConfig(name="gpt-4o", provider="openai", cost_per_1k=0.03, quality_score=95))
registry.register(ModelConfig(name="gpt-3.5-turbo", provider="openai", cost_per_1k=0.002, quality_score=70))
router = ModelRouter(registry, policy=RoutingPolicy.COST_OPTIMIZED)
result = router.select()  # → gpt-3.5-turbo (cheapest)

# Hook pipeline
hook_registry = HookRegistry()
hook_registry.register(HookEvent.AGENT_RUN, LoggingHook())
pipeline = HookPipeline(hook_registry)
outcome = pipeline.execute(HookEvent.AGENT_RUN, core=lambda: "done")

# Memory
memory = MemoryManager(InMemoryStore())
memory.remember("agent-1", "user_preference", "concise answers", ttl=3600)
assert memory.recall("agent-1", "user_preference") == "concise answers"
```

## Observability (Day 41-44)

`agentcook-core` defines two stdlib-only **hook surfaces** — modules
inside core call them; real OTel SDK / Langfuse SDK adapters live in
the application layer (`agentcook` main shell or
`agentcook-swarm/services/agent-core`):

| Surface | Module | Default | Application-layer adapter |
|---|---|---|---|
| Distributed tracing | `tracing` | `NoOpTracer` | `agentcook_app.otel_tracer_adapter.install()` |
| LLM observability   | `langfuse_hook` | `NoOpHook` | `agentcook_swarm/services/agent-core/langfuse_adapter.install()` |

In a microservice deployment (`docker-compose.staging.yml`), the
agent-core container's `setup_telemetry()`:

1. Boots the OTel SDK with OTLP gRPC export → otel-collector → Jaeger / Prometheus.
2. Calls `otel_tracer_adapter.install()` → core spans land in the same trace tree as the FastAPI request span.
3. Calls `langfuse_adapter.install()` → `model_router.select()` and `OpenAIProvider.chat()` report `generation` records to Langfuse.

Required environment variables (all optional — telemetry degrades to
NoOp if missing):

```
OTEL_SERVICE_NAME            agent-core | connector | admin-bff
OTEL_EXPORTER_OTLP_ENDPOINT  http://otel-collector:4317
DEPLOY_ENV                   dev | staging | prod
LANGFUSE_HOST                https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY          (Langfuse project public key)
LANGFUSE_SECRET_KEY          (Langfuse project secret key)
LANGFUSE_ENABLED             true | false (force NoOp without unsetting keys)
LOG_LEVEL                    DEBUG | INFO | WARNING | ERROR
```

Test seam: import `RecordingTracer` / `RecordingHook` from each
module's test file, install via `set_tracer()` / `set_langfuse_hook()`,
and assert what core would have reported — no SDK install needed.

## Design Principles

- **stdlib-only**: No runtime dependencies. Extension points via `Protocol`.
- **Async-first protocols**: I/O-bound methods are `async`. Sync wrappers are adapter concerns.
- **No engine lock-in**: LangGraph / google-adk / custom engines adapt to these protocols.
- **Frozen value types**: All dataclasses are `frozen=True` for thread safety.
- **Security-by-default**: Sandbox executor defaults to no-network, read-only rootfs, memory caps.
