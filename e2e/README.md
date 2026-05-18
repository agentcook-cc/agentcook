# e2e — Playwright end-to-end tests

Owner: Agent C (DevOps + 测试). Phase 2-5 主战场。

## Layout

- `playwright.config.ts` (in monorepo root) — Chromium / Firefox / WebKit projects.
- `e2e/*.spec.ts` — top-level e2e specs that exercise admin / app together.
- Per-app component tests live in `agentcook-admin/tests/` and `agentcook-app/tests/` via vitest.

## Run

```bash
# 1. start the dev server you want to test (admin shown)
pnpm --filter @agentcook-cc/admin dev

# 2. in a second terminal:
PLAYWRIGHT_BASE_URL=http://localhost:5173 pnpm e2e
```

CI runs against `staging.agentcook.cc` once that environment exists (Phase 4 Day 43).

## Adding a spec

Phase 1 baseline: 1 smoke test gated on `PLAYWRIGHT_BASE_URL`. The 5 core user
flows referenced in `agent-c-devops.md` (Phase 5 Day 48) will land here.
