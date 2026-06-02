# agentcook-providers

LLM provider adapters implementing `agentcook_core.LLMProviderProtocol`.
Single factory entry point with lazy vendor-SDK imports — installing this
package alone does not pull any vendor SDK; install the relevant extra to
activate a provider.

## Install

```bash
pip install agentcook-providers
# Optional vendor extras:
pip install 'agentcook-providers[openai]'  # also enables Qwen (same SDK)
```

## Provider Matrix

| Provider | Class | Status | Vendor SDK | Default Model |
|----------|-------|--------|-----------|---------------|
| OpenAI | `OpenAIProvider` | ✅ shipped | `openai>=1.30` | `gpt-4o-mini` |
| Qwen (DashScope) | reuses `OpenAIProvider` | ✅ shipped | `openai>=1.30` (OpenAI-compatible endpoint) | `qwen-turbo` |
| Echo | `EchoProvider` | ✅ shipped | none (stdlib) | `echo-v0` |
| Fallback chain | `FallbackProvider` | ✅ shipped | composes other providers | n/a |
| Anthropic | (not landed) | 🟡 `NotImplementedError` placeholder | `anthropic` (future) | `claude-sonnet-4-6` |
| Zhipu | (not landed) | 🟡 `NotImplementedError` placeholder | `zhipu` (future) | `glm-4-flash` |

`create_provider(name)` raises `NotImplementedError` for Anthropic / Zhipu
with a pointer to the backlog ticket — pass an alternative provider name
or implement the adapter and remove the raise.

## Factory Usage

```python
from agentcook_providers import create_provider

# Env-driven (production / docker): reads AGENTCOOK_LLM_PROVIDER, *_API_KEY, etc.
provider = create_provider()

# Explicit (notebooks / tests):
provider = create_provider(
    provider="qwen",
    model="qwen-plus",
    api_key="sk-...",          # falls back to QWEN_API_KEY / DASHSCOPE_API_KEY
    # base_url is auto-set to dashscope.aliyuncs.com/compatible-mode/v1
)

# All providers satisfy the same Protocol → no engine lock-in
async for chunk in provider.stream_chat(messages=[Message(role="user", content="hi")]):
    print(chunk.delta_content, end="", flush=True)
```

### Environment variables

| Variable | Used by | Notes |
|----------|---------|-------|
| `AGENTCOOK_LLM_PROVIDER` | factory dispatch | `openai` / `qwen` / `echo` / (`anthropic` / `zhipu` raise) |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` | OpenAI | `OPENAI_BASE_URL` lets you point at Azure / proxies |
| `QWEN_API_KEY` (or `DASHSCOPE_API_KEY`) / `QWEN_MODEL` / `QWEN_BASE_URL` | Qwen (via OpenAIProvider) | Defaults to DashScope compatible-mode endpoint |
| `AGENTCOOK_CHAT_MOCK=true` | `agentcook` main shell (not this package) | Routes `chat.py` to mock generator regardless of provider config |

## ADR References

| ADR | Topic |
|-----|-------|
| ADR-016 | Default LLM provider = Qwen (qwen-turbo). Cost / Chinese-first audience / DashScope free tier rationale. |
| ADR-017 | `/api/v1/chat/stream` endpoint integrates real LLM via `create_provider()` factory (Phase 4.6, 2026-06-01). Mock generator retained as `AGENTCOOK_CHAT_MOCK=true` fallback for unit/contract tests + offline dev. |

`qwen-turbo` is the documented default for two reasons:

1. **Cost**: DashScope free tier covers the educational use cases this
   project targets. OpenAI requires a paid account from request 1.
2. **Latency profile**: qwen-turbo p95 ≈ 1.8s for short prompts (Day 50
   100u baseline, see `audit/phase5-day50-performance-report.md`), good
   enough for SSE streaming demos.

Override the default with `AGENTCOOK_LLM_PROVIDER=openai` when running
in environments where DashScope is unreachable or when reproducing
ADR-002 / ADR-009 reference traces from upstream documentation.

## FallbackProvider

`FallbackProvider` composes any chain of `LLMProviderProtocol` instances
and retries on rate-limit / 5xx / overload errors. Useful for keeping
demos up when the primary vendor is unstable.

```python
from agentcook_providers import FallbackProvider, OpenAIProvider, create_provider

primary = create_provider(provider="qwen")
secondary = create_provider(provider="openai")
echo = create_provider(provider="echo")  # final fallback never fails

provider = FallbackProvider(providers=[primary, secondary, echo])
```

Retry policy: exponential backoff (100ms / 200ms / 400ms), max 3
attempts per provider, then advance to the next. The chain does not
retry on `ValueError` / `AuthenticationError` (configuration problems,
retrying makes them worse).

## Test Coverage (Day 50 spot check)

| Module | Line | Notes |
|--------|------|-------|
| `__init__.py` | 100% | re-exports only |
| `echo_provider.py` | 89% | — |
| `openai_provider.py` | 68% | 🟡 exception paths + tool_calls branch underspecified — Phase 5 backlog |
| `factory.py` | 82% | 🟡 Anthropic / Zhipu raise branches partially uncovered |
| `fallback.py` | 58% | 🟡 retry chain L118-142 underspecified — Phase 5 backlog |

Coverage gaps are tracked in `_internal/progress/progress-agent-a-day-50.md`
§1; the plan is to apply the `test_stream_real_response_metadata.py`
fixture pattern (FakeProvider injecting `raise`) once the Phase 5 buffer
window opens.

## Adding a New Provider

1. Add `myvendor_provider.py` implementing `LLMProviderProtocol`
   (`chat()` + `stream_chat()` + `model_name` attribute).
2. Wire it into `factory.create_provider` with a `if provider == "myvendor"`
   branch, including `_DEFAULT_MODELS["myvendor"]` and the relevant env
   vars (`MYVENDOR_API_KEY` / `MYVENDOR_BASE_URL` / `MYVENDOR_MODEL`).
3. Add `myvendor` to the `Supported:` list in the `ValueError` raised at
   the bottom of `factory.py`.
4. Add tests under `agentcook-providers/tests/test_myvendor_provider.py`
   using the FakeProvider pattern from
   `agentcook/tests/test_stream_real_response_metadata.py` — no live
   API calls in CI.
5. Document the addition under "Provider Matrix" and (if it changes
   defaults) draft a new ADR.
