# agentcook-starter

> **Status**: 🟡 Repository placeholder. The Python package is not yet
> published — the curated 545-line educational subset is planned for
> **Phase 6** to coincide with the public release of
> *《从 0 到 1 构建商业级 AI Agent 产品》*.
> Use [`agentcook`](../agentcook) (the full FastAPI shell) for any
> working today.

## What `agentcook-starter` Will Be

A curated subset of `agentcook-cc` packaged as a single installable
project, sized to be readable end-to-end in one sitting (≈ 545 lines of
Python). The intent is the same as Java's `mall-tiny`: keep the
architectural shape of the real product, drop everything you can defer.

The slim version will include:

| Layer | Trimmed from full `agentcook-cc` |
|-------|----------------------------------|
| Agent loop | Single-agent loop only (no multi-agent orchestrator) |
| LLM provider | One adapter (Qwen via OpenAI-compat) |
| Storage | In-memory store + optional SQLite (no pgvector / Redis / S3) |
| Memory | Two-layer (Soul + short-term events; no Diary) |
| Tools | Plugin sandbox dropped — direct in-process callables only |
| Observability | stdlib logging only (no OTel / Langfuse) |
| Auth | No JWT; single dev user |

This trade-off is deliberate: the goal is to teach the *shape* of an
agent harness without the operational depth Phase 4 added. Production
users should depend on [`agentcook`](../agentcook) +
[`agentcook-core`](../agentcook-core) directly.

## Why It Doesn't Ship Yet

- **Phase 5 priority is testing pyramid + compliance + DevOps docs**,
  not the curated educational fork.
- The "545 lines" target requires the full system to be feature-stable
  first — otherwise we'd churn the starter every time `agentcook-core`
  evolves. Phase 4 + Phase 4.6 (chat → real Qwen) only stabilised on
  2026-06-01.
- The companion tutorial chapters need to be locked before the starter
  picks its trimming line — splitting too early creates two sources of
  truth that drift.

## Roadmap

| Phase | What lands here |
|-------|------------------|
| **Phase 6** (post-tutorial publication) | Initial cut: `pyproject.toml` + `src/agentcook_starter/` ≈ 545 LOC + chapter-aligned examples |
| Phase 6.1 | Reproducibility CI (`pytest agentcook-starter/` is the only check) |
| Phase 6.2 | PyPI release; tutorial README points new readers here |

See [`_internal/agent-roles/agent-a-architect.md`](../agentcook-cc) and
the project roadmap for the full sequencing.

## Until Then

Start with the full project instead:

```bash
git clone https://github.com/agentcook-cc/agentcook-cc.git
cd agentcook-cc
uv sync
uv run pytest agentcook-core agentcook-providers -q
```

The first three modules to read are
`agentcook-core/src/agentcook_core/protocols.py` (interface shapes),
`agentcook-providers/src/agentcook_providers/openai_provider.py`
(reference LLM adapter), and
`agentcook/src/agentcook_app/main.py` (FastAPI wiring).
