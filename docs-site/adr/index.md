# Architecture Decision Records

ADRs capture the *why* behind agentcook's structural choices. Each record
describes the context, the alternatives we considered, the decision, and
the consequences.

The canonical copies live in the repository under `docs/adr/` — this page
mirrors the index so the same set is discoverable from the docs site.

## Index

| # | Title | Topic |
|---|-------|-------|
| ADR-001 | [Multi-package monorepo](https://github.com/agentcook-cc/agentcook/blob/main/docs/adr/ADR-001-multi-package.md) | Repo structure |
| ADR-002 | [LangGraph integration](https://github.com/agentcook-cc/agentcook/blob/main/docs/adr/ADR-002-langgraph-integration.md) | Agent orchestration |
| ADR-003 | [Design tokens](https://github.com/agentcook-cc/agentcook/blob/main/docs/adr/ADR-003-design-tokens.md) | Shared visual primitives |
| ADR-004 | [Plugin sandbox](https://github.com/agentcook-cc/agentcook/blob/main/docs/adr/ADR-004-plugin-sandbox.md) | Tool isolation |
| ADR-005 | [Observability stack](https://github.com/agentcook-cc/agentcook/blob/main/docs/adr/ADR-005-observability-stack.md) | OTel + Jaeger + Prometheus + Langfuse |
| ADR-006 | [Blue/green deployment](https://github.com/agentcook-cc/agentcook/blob/main/docs/adr/ADR-006-blue-green-deployment.md) | Release strategy |
| ADR-007 | [Test pyramid](https://github.com/agentcook-cc/agentcook/blob/main/docs/adr/ADR-007-test-pyramid.md) | Unit / integration / contract / e2e |
| ADR-008 | [API versioning](https://github.com/agentcook-cc/agentcook/blob/main/docs/adr/ADR-008-api-versioning.md) | URL-path `/v1`, semver, freeze + bump |
| ADR-009 | [Parallel frontends](https://github.com/agentcook-cc/agentcook/blob/main/docs/adr/ADR-009-parallel-frontend.md) | admin (Vue) vs app (React) |
| ADR-010 | [Desktop distribution](https://github.com/agentcook-cc/agentcook/blob/main/docs/adr/ADR-010-desktop-distribution.md) | Electron packaging |
| ADR-011 | [Agent memory](https://github.com/agentcook-cc/agentcook/blob/main/docs/adr/ADR-011-agent-memory.md) | Four-layer Identity/Soul/Memory/Diary |
| ADR-012 | [Agent harness philosophy](https://github.com/agentcook-cc/agentcook/blob/main/docs/adr/ADR-012-agent-harness-philosophy.md) | 9-dimension framework |
| ADR-013 | [Java business backend](https://github.com/agentcook-cc/agentcook/blob/main/docs/adr/ADR-013-java-business-backend.md) | Python ↔ Java boundary |

## How to read these

Each ADR follows the [Michael Nygard
template](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions):
**Context** describes the forces at play, **Decision** is the chosen
option, **Consequences** are the trade-offs we are now living with.

When a decision changes, we don't edit the old ADR — we add a new one
that supersedes it. Status fields at the top indicate `proposed`,
`accepted`, `superseded by ADR-NNN`.

## Proposing a new ADR

```bash
cp docs/adr/ADR-XXX-template.md docs/adr/ADR-014-your-topic.md
# fill in context / decision / consequences
git add docs/adr/ADR-014-your-topic.md
git commit -m "ADR-014: short description"
```

Open a PR — at least one reviewer should sign off before merging.
