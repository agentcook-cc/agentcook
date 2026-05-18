# agentcook-core · Tests

This package's tests are pure-Python contract tests. They **do not** depend
on Docker, PostgreSQL, Redis, or network access — running `pytest -m unit`
from the monorepo root finishes in milliseconds.

## How tests connect to the monorepo test infrastructure

The shared `conftest.py` lives at the **monorepo root**
(`agentcook-cc/conftest.py`), authored by Agent C. With
`--import-mode=importlib` configured in the top-level `pyproject.toml`,
pytest auto-discovers it for every test under any package's `tests/`
directory — **no per-package copy is needed.**

It exposes these fixtures (all requiring Docker; see C's docstrings for
exact semantics):

| Fixture | Scope | Provides | Notes |
|---|---|---|---|
| `pg_container` | session | running `postgres:16-alpine` | one container per `pytest` run |
| `redis_container` | session | running `redis:7-alpine` | one container per `pytest` run |
| `pg_url` | function | SQLAlchemy URL string | derived from `pg_container` |
| `db_session` | function | open `psycopg.Connection` | rolled back at teardown |
| `redis_client` | function | `redis.Redis` client | `FLUSHDB` before yielding |

If the Docker daemon is unreachable, the session-scoped fixtures
gracefully **skip** instead of erroring — unit tests stay green on
machines without Docker.

## Markers

The monorepo `pyproject.toml` registers three markers:

- `unit` — fast tests, no external dependencies. **All tests in this
  package are `unit`.** Module-level: `pytestmark = pytest.mark.unit`.
- `integration` — requires Docker; tests opt in via the fixtures above.
- `slow` — tests taking >5s.

## Running

```bash
# All unit tests across the monorepo (includes this package)
uv run pytest -m unit

# Just this package
uv run --package agentcook-core pytest agentcook-core

# Integration tier (skipped if Docker is down)
uv run pytest -m integration
```

## What `agentcook-core` tests do not use (and why)

`agentcook-core` defines structural protocols and frozen dataclasses
only — there is no I/O, no LLM calls, no DB, no Redis. It therefore
**does not request any of Agent C's fixtures**. If a future change adds
a feature that needs PostgreSQL or Redis (it shouldn't — that belongs in
`agentcook-storage`), reach for `db_session` / `redis_client` instead of
spinning up your own container.

## Message field semantics (Day 8 update)

`Message` carries optional tool-use fields. The semantics (and what
`test_protocols.py` exercises) are:

| Field | Used by | When |
|---|---|---|
| `name` | `system` / `user` / `tool` | participant or tool name |
| `tool_calls` | `assistant` | model requested one or more tools |
| `tool_call_id` | `tool` | binds a tool reply to its request |

`ToolCall` is a frozen dataclass with `id`, `name`, `arguments` (parsed
JSON dict). Providers serialize/deserialize the wire form. See
`agentcook-providers/tests/test_providers.py::test_openai_provider_serializes_tool_reply_correctly`
for the canonical OpenAI mapping.
