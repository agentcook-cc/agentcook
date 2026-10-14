"""agentcook-storage: backend-agnostic storage protocols + default PG/Redis/S3 impls.

Public API:

- :class:`SqlStoreProtocol` / :class:`KeyValueStoreProtocol` /
  :class:`ObjectStoreProtocol` — the three transport-level protocols.
- :class:`PostgresStore` + :func:`ensure_pgvector_extension` — default
  relational backend with pgvector helper (ADR-011 v1 default).
- :class:`RedisStore` — default key-value backend.
- :class:`S3ObjectStore` — default object-store backend (works with
  AWS S3 / MinIO / Cloudflare R2 / LocalStack).
- :class:`PgConversationStore` — conversation transcripts (multi-turn
  chat history incl. tool calls) with per-user ownership.
- :class:`HashingEmbedder` — zero-dependency lexical embedder (default
  for pgvector recall when no embedding API is configured).

Default backends are imported lazily through their respective modules,
so ``import agentcook_storage`` does *not* require asyncpg / redis /
aioboto3 to be installed.
"""

from __future__ import annotations

from agentcook_storage.conversation_store import CONVERSATIONS_DDL, PgConversationStore
from agentcook_storage.embeddings import HashingEmbedder, OpenAICompatibleEmbedder
from agentcook_storage.memory_store import Embedder, PgVectorMemoryStore
from agentcook_storage.postgres import PostgresStore, ensure_pgvector_extension
from agentcook_storage.protocols import (
    KeyValueStoreProtocol,
    ObjectStoreProtocol,
    SqlStoreProtocol,
)
from agentcook_storage.redis_store import RedisStore
from agentcook_storage.s3 import S3ObjectStore

__version__ = "0.2.0"

__all__ = [
    "CONVERSATIONS_DDL",
    "Embedder",
    "HashingEmbedder",
    "KeyValueStoreProtocol",
    "ObjectStoreProtocol",
    "OpenAICompatibleEmbedder",
    "PgConversationStore",
    "PgVectorMemoryStore",
    "PostgresStore",
    "RedisStore",
    "S3ObjectStore",
    "SqlStoreProtocol",
    "__version__",
    "ensure_pgvector_extension",
]
