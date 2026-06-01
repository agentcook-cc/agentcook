"""Four-layer Memory system — Identity / Soul / Memory / Diary.

Implements the agentcook memory model inspired by human cognitive layers:

- **Identity** (Layer 1): Immutable agent persona — who the agent IS.
  Loaded from YAML/JSON at startup, never mutated at runtime.
- **Soul** (Layer 2): Stable personality traits — adjustable but versioned.
  Long-term preferences, communication style, learned behaviors.
- **Memory** (Layer 3): Working memory — session-scoped KV with TTL.
  Short-term context for ongoing conversations.
- **Diary** (Layer 4): Long-term episodic memory — append-only event log.
  Experiences, decisions, reflections for semantic recall.

Design:
- stdlib-only (no third-party imports).
- ``MemoryStore`` Protocol — injected persistence backend.
- ``EmbeddingProvider`` Protocol — injected embedding for semantic search.
- All layers share a unified ``MemoryEntry`` format for storage uniformity.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from agentcook_core.tracing import get_tracer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Value Types
# ---------------------------------------------------------------------------


class MemoryLayer(str, Enum):
    """The four cognitive layers of agent memory."""

    IDENTITY = "identity"
    SOUL = "soul"
    MEMORY = "memory"
    DIARY = "diary"


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    """A single entry in any memory layer.

    Attributes:
        layer: Which cognitive layer this entry belongs to.
        key: Unique identifier within the layer (e.g. "persona.name").
        content: The actual content (text, JSON string, etc.).
        embedding_ref: Optional reference to a stored embedding vector.
        timestamp: Unix timestamp of creation/last update.
        ttl: Time-to-live in seconds (0 = never expires).
        metadata: Arbitrary key-value pairs for filtering/indexing.
    """

    layer: MemoryLayer
    key: str
    content: str
    embedding_ref: str | None = None
    timestamp: float = field(default_factory=time.time)
    ttl: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if this entry has exceeded its TTL."""
        if self.ttl <= 0:
            return False
        return (time.time() - self.timestamp) > self.ttl


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Result of a semantic search across memory layers."""

    entry: MemoryEntry
    score: float
    source_layer: MemoryLayer


class MemoryError(Exception):
    """Raised on memory operation failures."""


# ---------------------------------------------------------------------------
# Protocols (injectable)
# ---------------------------------------------------------------------------


@runtime_checkable
class MemoryStore(Protocol):
    """Persistence backend for memory entries.

    Implementations may use Redis, PostgreSQL, SQLite, or in-memory dicts.
    The protocol is intentionally synchronous for simplicity in the core
    package; async adapters wrap this in downstream packages.
    """

    def write(self, agent_id: str, entry: MemoryEntry) -> None:
        """Persist or update a memory entry."""
        ...

    def read(self, agent_id: str, layer: MemoryLayer, key: str) -> MemoryEntry | None:
        """Read a single entry by layer + key. Returns None if absent."""
        ...

    def list_entries(
        self,
        agent_id: str,
        layer: MemoryLayer,
        *,
        prefix: str | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        """List entries in a layer, optionally filtered by key prefix."""
        ...

    def delete(self, agent_id: str, layer: MemoryLayer, key: str) -> bool:
        """Delete an entry. Returns True if it existed."""
        ...

    def expire(self, agent_id: str) -> int:
        """Remove all expired entries for an agent. Returns count removed."""
        ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Injected embedding generator for semantic search."""

    def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text."""
        ...

    def similarity(self, vector_a: list[float], vector_b: list[float]) -> float:
        """Compute similarity score between two vectors (0..1)."""
        ...


# ---------------------------------------------------------------------------
# In-Memory Store (default / testing)
# ---------------------------------------------------------------------------


class InMemoryStore:
    """Simple dict-backed store for testing and development."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, MemoryEntry]] = {}

    def _agent_key(self, agent_id: str, layer: MemoryLayer, key: str) -> str:
        return f"{agent_id}:{layer.value}:{key}"

    def write(self, agent_id: str, entry: MemoryEntry) -> None:
        compound_key = self._agent_key(agent_id, entry.layer, entry.key)
        self._data.setdefault(agent_id, {})[compound_key] = entry

    def read(self, agent_id: str, layer: MemoryLayer, key: str) -> MemoryEntry | None:
        compound_key = self._agent_key(agent_id, layer, key)
        agent_entries = self._data.get(agent_id, {})
        entry = agent_entries.get(compound_key)
        if entry and entry.is_expired:
            del agent_entries[compound_key]
            return None
        return entry

    def list_entries(
        self,
        agent_id: str,
        layer: MemoryLayer,
        *,
        prefix: str | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        agent_entries = self._data.get(agent_id, {})
        layer_prefix = f"{agent_id}:{layer.value}:"
        results: list[MemoryEntry] = []

        for compound_key, entry in list(agent_entries.items()):
            if not compound_key.startswith(layer_prefix):
                continue
            if entry.is_expired:
                del agent_entries[compound_key]
                continue
            if prefix and not entry.key.startswith(prefix):
                continue
            results.append(entry)
            if len(results) >= limit:
                break

        return results

    def delete(self, agent_id: str, layer: MemoryLayer, key: str) -> bool:
        compound_key = self._agent_key(agent_id, layer, key)
        agent_entries = self._data.get(agent_id, {})
        if compound_key in agent_entries:
            del agent_entries[compound_key]
            return True
        return False

    def expire(self, agent_id: str) -> int:
        agent_entries = self._data.get(agent_id, {})
        expired_keys = [k for k, e in agent_entries.items() if e.is_expired]
        for key in expired_keys:
            del agent_entries[key]
        return len(expired_keys)


# ---------------------------------------------------------------------------
# IdentityLoader
# ---------------------------------------------------------------------------


class IdentityLoader:
    """Loads Identity layer entries from structured data (YAML/JSON).

    Identity is immutable at runtime — loaded once at agent initialization.
    Supports dict input (parsed YAML/JSON) or raw JSON string.
    """

    def load_from_dict(self, agent_id: str, data: dict[str, Any], store: MemoryStore) -> int:
        """Load identity entries from a dict. Returns count of entries written.

        Expected structure:
            {
                "name": "...",
                "role": "...",
                "description": "...",
                "constraints": ["...", "..."],
                ...
            }
        Each top-level key becomes a MemoryEntry in the IDENTITY layer.
        """
        count = 0
        for key, value in data.items():
            content = json.dumps(value) if not isinstance(value, str) else value
            entry = MemoryEntry(
                layer=MemoryLayer.IDENTITY,
                key=key,
                content=content,
                ttl=0,  # Identity never expires
            )
            store.write(agent_id, entry)
            count += 1

        logger.debug("Loaded %d identity entries for agent %s", count, agent_id)
        return count

    def load_from_json(self, agent_id: str, json_string: str, store: MemoryStore) -> int:
        """Parse JSON string and load as identity entries."""
        try:
            data = json.loads(json_string)
        except json.JSONDecodeError as exc:
            raise MemoryError(f"Invalid JSON for identity: {exc}") from exc

        if not isinstance(data, dict):
            raise MemoryError("Identity JSON must be a top-level object")

        return self.load_from_dict(agent_id, data, store)


# ---------------------------------------------------------------------------
# SoulManager
# ---------------------------------------------------------------------------


class SoulManager:
    """Manages the Soul layer — stable personality traits.

    Soul entries are versioned conceptually (each write is a new frozen entry).
    Supports CRUD operations + bulk trait management.
    """

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def set_trait(self, agent_id: str, key: str, value: str, *, metadata: dict[str, Any] | None = None) -> None:
        """Set or update a soul trait."""
        entry = MemoryEntry(
            layer=MemoryLayer.SOUL,
            key=key,
            content=value,
            ttl=0,  # Soul traits don't expire
            metadata=metadata or {},
        )
        self._store.write(agent_id, entry)

    def get_trait(self, agent_id: str, key: str) -> str | None:
        """Get a soul trait value. Returns None if absent."""
        entry = self._store.read(agent_id, MemoryLayer.SOUL, key)
        return entry.content if entry else None

    def list_traits(self, agent_id: str, *, prefix: str | None = None) -> dict[str, str]:
        """List all soul traits as key → value mapping."""
        entries = self._store.list_entries(agent_id, MemoryLayer.SOUL, prefix=prefix)
        return {e.key: e.content for e in entries}

    def delete_trait(self, agent_id: str, key: str) -> bool:
        """Remove a soul trait. Returns True if it existed."""
        return self._store.delete(agent_id, MemoryLayer.SOUL, key)

    def bulk_set(self, agent_id: str, traits: dict[str, str]) -> int:
        """Set multiple traits at once. Returns count written."""
        for key, value in traits.items():
            self.set_trait(agent_id, key, value)
        return len(traits)


# ---------------------------------------------------------------------------
# MemoryManager
# ---------------------------------------------------------------------------


class MemoryManager:
    """Unified entry point for all four memory layers.

    Orchestrates reads/writes across layers with consistent semantics.
    Optionally integrates an EmbeddingProvider for semantic search.
    """

    def __init__(
        self,
        store: MemoryStore,
        *,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._store = store
        self._embedder = embedding_provider
        self._identity_loader = IdentityLoader()
        self._soul_manager = SoulManager(store)

    @property
    def store(self) -> MemoryStore:
        return self._store

    @property
    def soul(self) -> SoulManager:
        return self._soul_manager

    @property
    def identity_loader(self) -> IdentityLoader:
        return self._identity_loader

    # --- Write Operations ---

    def write_to_layer(
        self,
        agent_id: str,
        layer: MemoryLayer,
        key: str,
        content: str,
        *,
        ttl: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """Write an entry to any layer.

        For IDENTITY layer, prefer using IdentityLoader.
        For SOUL layer, prefer using SoulManager.
        """
        with get_tracer().start_span(
            f"memory.{layer.value}.write",
            attributes={
                "agentcook.memory.agent_id": agent_id,
                "agentcook.memory.layer": layer.value,
                "agentcook.memory.key": key,
                "agentcook.memory.ttl": ttl,
            },
        ):
            embedding_ref: str | None = None
            if self._embedder and layer in (MemoryLayer.DIARY, MemoryLayer.MEMORY):
                # Generate embedding for searchable layers
                embedding_ref = f"emb:{agent_id}:{layer.value}:{key}"

            entry = MemoryEntry(
                layer=layer,
                key=key,
                content=content,
                embedding_ref=embedding_ref,
                ttl=ttl,
                metadata=metadata or {},
            )
            self._store.write(agent_id, entry)
            logger.debug("Wrote to %s layer: %s/%s", layer.value, agent_id, key)
            return entry

    # --- Read Operations ---

    def read_from_layer(self, agent_id: str, layer: MemoryLayer, key: str) -> MemoryEntry | None:
        """Read a single entry from a specific layer."""
        with get_tracer().start_span(
            f"memory.{layer.value}.read",
            attributes={
                "agentcook.memory.agent_id": agent_id,
                "agentcook.memory.layer": layer.value,
                "agentcook.memory.key": key,
            },
        ) as span:
            entry = self._store.read(agent_id, layer, key)
            span.set_attribute("agentcook.memory.hit", entry is not None)
            return entry

    def list_layer(
        self,
        agent_id: str,
        layer: MemoryLayer,
        *,
        prefix: str | None = None,
        limit: int = 100,
    ) -> list[MemoryEntry]:
        """List entries in a layer."""
        return self._store.list_entries(agent_id, layer, prefix=prefix, limit=limit)

    # --- Semantic Search ---

    def semantic_search(
        self,
        agent_id: str,
        query: str,
        *,
        layers: Sequence[MemoryLayer] | None = None,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Search memory by semantic similarity.

        Requires an EmbeddingProvider to be configured.
        Searches MEMORY and DIARY layers by default.
        """
        if not self._embedder:
            raise MemoryError("No EmbeddingProvider configured for semantic search")

        search_layers = layers or [MemoryLayer.MEMORY, MemoryLayer.DIARY]
        with get_tracer().start_span(
            "memory.semantic_search",
            attributes={
                "agentcook.memory.agent_id": agent_id,
                "agentcook.memory.query.length": len(query),
                "agentcook.memory.layers": ",".join(l.value for l in search_layers),
                "agentcook.memory.top_k": top_k,
            },
        ) as span:
            query_vector = self._embedder.embed(query)

            candidates: list[SearchResult] = []
            for layer in search_layers:
                entries = self._store.list_entries(agent_id, layer, limit=1000)
                for entry in entries:
                    if entry.embedding_ref:
                        entry_vector = self._embedder.embed(entry.content)
                        score = self._embedder.similarity(query_vector, entry_vector)
                        candidates.append(SearchResult(
                            entry=entry,
                            score=score,
                            source_layer=layer,
                        ))

            # Sort by score descending, return top_k
            candidates.sort(key=lambda r: r.score, reverse=True)
            results = candidates[:top_k]
            span.set_attribute("agentcook.memory.hit_count", len(results))
            return results

    # --- Garbage Collection ---

    def gc(self, agent_id: str) -> int:
        """Expire stale entries across all layers. Returns count removed."""
        removed = self._store.expire(agent_id)
        if removed > 0:
            logger.info("GC removed %d expired entries for agent %s", removed, agent_id)
        return removed

    # --- Diary Convenience ---

    def append_diary(
        self,
        agent_id: str,
        content: str,
        *,
        key: str | None = None,
        ttl: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """Append an entry to the Diary layer (episodic memory).

        If no key is provided, generates a timestamp-based key.
        """
        entry_key = key or f"diary_{int(time.time() * 1000)}"
        return self.write_to_layer(
            agent_id,
            MemoryLayer.DIARY,
            entry_key,
            content,
            ttl=ttl,
            metadata=metadata,
        )

    # --- Working Memory Convenience ---

    def remember(
        self,
        agent_id: str,
        key: str,
        content: str,
        *,
        ttl: int = 3600,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """Write to working Memory layer with default 1-hour TTL."""
        return self.write_to_layer(
            agent_id,
            MemoryLayer.MEMORY,
            key,
            content,
            ttl=ttl,
            metadata=metadata,
        )

    def recall(self, agent_id: str, key: str) -> str | None:
        """Read from working Memory layer. Returns content or None."""
        entry = self.read_from_layer(agent_id, MemoryLayer.MEMORY, key)
        return entry.content if entry else None


__all__ = [
    "EmbeddingProvider",
    "IdentityLoader",
    "InMemoryStore",
    "MemoryEntry",
    "MemoryError",
    "MemoryLayer",
    "MemoryManager",
    "MemoryStore",
    "SearchResult",
    "SoulManager",
]
