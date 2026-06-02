# agentcook-storage

Storage backends for the agentcook runtime. Three transport-level
protocols (SQL / KV / object store) with default implementations for
PostgreSQL + pgvector, Redis, and S3-compatible object stores. Sits
between `agentcook-core` (which defines `MemoryStore` Protocol) and
the FastAPI shell in `agentcook` (which wires concrete instances at
startup).

## Install

```bash
pip install agentcook-storage
# Vendor extras — install only what you need:
pip install 'agentcook-storage[postgres]'   # asyncpg + pgvector helper
pip install 'agentcook-storage[redis]'      # redis-py async client
pip install 'agentcook-storage[s3]'         # aioboto3 (works with MinIO / R2 / LocalStack)
```

The base install pulls **nothing** — every vendor SDK is lazy-imported
through its module, so `import agentcook_storage` succeeds on a clean
Python install. Calling `PostgresStore.from_dsn(...)` without
`asyncpg` raises `ImportError` with a clear extras hint.

## Modules

| Module | Purpose | Default | Vendor SDK |
|--------|---------|---------|-----------|
| `protocols` | 3 transport-level Protocol classes | `SqlStoreProtocol`, `KeyValueStoreProtocol`, `ObjectStoreProtocol` | none |
| `postgres` | asyncpg connection pool wrapping + pgvector extension bootstrap | `PostgresStore`, `ensure_pgvector_extension` | `asyncpg>=0.29` |
| `redis_store` | Async Redis client wrapper | `RedisStore` | `redis>=5.0` |
| `s3` | Async S3-compatible object store (works with AWS S3 / MinIO / Cloudflare R2 / LocalStack) | `S3ObjectStore` | `aioboto3>=12.0` |
| `memory_store` | `agentcook_core.MemoryStore` implementation backed by pgvector | `PgVectorMemoryStore`, `Embedder` (Protocol) | pulls `postgres` extras |

## Architecture (ADR-011)

```
┌──────────────────────────────────────────────────┐
│ agentcook-core  (defines MemoryStore Protocol)   │
└────────────────────┬─────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
┌──────────────┐         ┌──────────────────┐
│ agentcook    │         │ agentcook-storage │
│ (FastAPI)    │ uses →  │ PgVectorMemoryStore (default)
│ create_app() │         │ + PostgresStore    │
└──────────────┘         │ + RedisStore       │
                          │ + S3ObjectStore    │
                          └──────────────────┘
```

`agentcook-storage` does not own any runtime API surface — it provides
the concrete *implementations* of the `MemoryStore` Protocol that
`agentcook-core` declares, plus thin pool wrappers for the three
backing services. Other consumers (CLI tools, batch jobs, future
swarm services) can compose the same primitives without going through
the FastAPI shell.

## Quick Start

### PostgreSQL + pgvector memory store

```python
import asyncio
from agentcook_storage import PostgresStore, PgVectorMemoryStore, ensure_pgvector_extension


class MyEmbedder:
    async def embed(self, text: str) -> list[float]:
        # In production: call OpenAI text-embedding-3-small or Qwen embedding.
        return [0.0] * 1536


async def main() -> None:
    store = await PostgresStore.from_dsn(
        "postgresql://agentcook:agentcook@localhost:5432/agentcook",
        max_size=20,
    )
    await ensure_pgvector_extension(store)
    memory = PgVectorMemoryStore(store=store, embedder=MyEmbedder())

    await memory.remember(
        agent_id="agt-001",
        key="user_preference",
        content="concise answers",
    )
    hits = await memory.recall(agent_id="agt-001", query="how should I answer?", k=5)
    for hit in hits:
        print(hit.content, hit.score)


asyncio.run(main())
```

### Redis short-term cache

```python
from agentcook_storage import RedisStore

cache = await RedisStore.from_url("redis://localhost:6379/0")
await cache.set("session:abc", "user-123", ttl_seconds=900)
user = await cache.get("session:abc")
```

### S3 object store

```python
from agentcook_storage import S3ObjectStore

bucket = await S3ObjectStore.from_config(
    bucket="agentcook-uploads",
    endpoint_url="http://localhost:9000",   # MinIO; omit for AWS S3
    access_key="minioadmin",
    secret_key="minioadmin",
)
key = await bucket.put_object(key="plugins/foo.zip", body=open("foo.zip", "rb").read())
```

## ADR References

| ADR | Topic |
|-----|-------|
| ADR-008 | Four-layer memory (Identity / Soul / Memory / Diary) — the layer model `PgVectorMemoryStore` implements |
| ADR-011 | Agent memory storage choice = PostgreSQL + pgvector (rather than Pinecone / Weaviate / Milvus) |

Reasons captured in ADR-011: operational simplicity (one Postgres
beats a separate vector DB), `agentcook-business` already needs
Postgres for User/Plugin/Connector aggregates, and pgvector handles
the scale targets through `iv_flat` indexes (`Phase 5 backlog` —
ANN index sized for production embeddings is on the Phase 5/6 list,
see `progress-agent-a-day-50.md` §1).

## Version Compatibility

Tracks `agentcook-core ^0.x` (pre-1.0: pinned to exact MINOR).
Protocol shapes (`SqlStoreProtocol` / `KeyValueStoreProtocol` /
`ObjectStoreProtocol` / `MemoryStore`) match core verbatim — when
core MINOR bumps, this package re-pins the same MINOR.

| Backend | Tested SDK range |
|---------|------------------|
| `asyncpg` | `>=0.29,<0.30` |
| `redis-py` | `>=5.0,<6.0` |
| `aioboto3` | `>=12.0,<13.0` |
| PostgreSQL server | 14+ (pgvector 0.5+) |
| Redis server | 6+ |

## Testing

```bash
# Unit tests against mocked clients (no live backends required):
uv run pytest agentcook-storage -q

# Integration tests with testcontainers (requires Docker):
uv run pytest agentcook-storage -m integration -q
```

Test coverage 92% (Day 50 spot check). The Embedder Protocol uses a
deterministic fake under unit tests; integration suite spins real
Postgres + pgvector through `testcontainers-python`.
