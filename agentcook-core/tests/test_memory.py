"""Unit tests for agentcook_core.memory module."""

from __future__ import annotations

import json
import time

import pytest
from agentcook_core.memory import (
    EmbeddingProvider,
    IdentityLoader,
    InMemoryStore,
    MemoryEntry,
    MemoryError,
    MemoryLayer,
    MemoryManager,
    MemoryStore,
    SearchResult,
    SoulManager,
)

# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


class FakeEmbedder:
    """Simple embedder that uses character frequency as 'vector'."""

    def embed(self, text: str) -> list[float]:
        # Deterministic 26-dim vector based on char frequency
        vec = [0.0] * 26
        for ch in text.lower():
            if "a" <= ch <= "z":
                vec[ord(ch) - ord("a")] += 1.0
        # Normalize
        total = sum(vec) or 1.0
        return [v / total for v in vec]

    def similarity(self, vector_a: list[float], vector_b: list[float]) -> float:
        # Cosine similarity
        dot = sum(a * b for a, b in zip(vector_a, vector_b))
        mag_a = sum(a * a for a in vector_a) ** 0.5
        mag_b = sum(b * b for b in vector_b) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# MemoryEntry Tests
# ---------------------------------------------------------------------------


class TestMemoryEntry:
    def test_frozen_immutable(self):
        entry = MemoryEntry(layer=MemoryLayer.IDENTITY, key="name", content="Alice")
        with pytest.raises(AttributeError):
            entry.key = "other"  # type: ignore[misc]

    def test_is_expired_false_when_no_ttl(self):
        entry = MemoryEntry(layer=MemoryLayer.MEMORY, key="k", content="v", ttl=0)
        assert entry.is_expired is False

    def test_is_expired_false_when_within_ttl(self):
        entry = MemoryEntry(
            layer=MemoryLayer.MEMORY, key="k", content="v",
            timestamp=time.time(), ttl=3600,
        )
        assert entry.is_expired is False

    def test_is_expired_true_when_past_ttl(self):
        entry = MemoryEntry(
            layer=MemoryLayer.MEMORY, key="k", content="v",
            timestamp=time.time() - 10, ttl=5,
        )
        assert entry.is_expired is True

    def test_default_timestamp_set(self):
        entry = MemoryEntry(layer=MemoryLayer.DIARY, key="k", content="v")
        assert entry.timestamp > 0

    def test_metadata_default_empty(self):
        entry = MemoryEntry(layer=MemoryLayer.SOUL, key="k", content="v")
        assert entry.metadata == {}


# ---------------------------------------------------------------------------
# MemoryLayer Tests
# ---------------------------------------------------------------------------


class TestMemoryLayer:
    def test_all_layers(self):
        assert {l.value for l in MemoryLayer} == {"identity", "soul", "memory", "diary"}

    def test_string_enum(self):
        assert MemoryLayer.IDENTITY == "identity"
        assert isinstance(MemoryLayer.SOUL, str)


# ---------------------------------------------------------------------------
# InMemoryStore Tests
# ---------------------------------------------------------------------------


class TestInMemoryStore:
    def test_write_and_read(self):
        store = InMemoryStore()
        entry = MemoryEntry(layer=MemoryLayer.IDENTITY, key="name", content="Agent-1")
        store.write("agent-1", entry)
        result = store.read("agent-1", MemoryLayer.IDENTITY, "name")
        assert result == entry

    def test_read_nonexistent(self):
        store = InMemoryStore()
        assert store.read("agent-1", MemoryLayer.IDENTITY, "missing") is None

    def test_read_expired_returns_none(self):
        store = InMemoryStore()
        entry = MemoryEntry(
            layer=MemoryLayer.MEMORY, key="temp", content="v",
            timestamp=time.time() - 10, ttl=5,
        )
        store.write("agent-1", entry)
        assert store.read("agent-1", MemoryLayer.MEMORY, "temp") is None

    def test_list_entries_filters_by_layer(self):
        store = InMemoryStore()
        store.write("a", MemoryEntry(layer=MemoryLayer.IDENTITY, key="k1", content="v1"))
        store.write("a", MemoryEntry(layer=MemoryLayer.SOUL, key="k2", content="v2"))
        store.write("a", MemoryEntry(layer=MemoryLayer.IDENTITY, key="k3", content="v3"))

        results = store.list_entries("a", MemoryLayer.IDENTITY)
        assert len(results) == 2
        assert all(e.layer == MemoryLayer.IDENTITY for e in results)

    def test_list_entries_with_prefix(self):
        store = InMemoryStore()
        store.write("a", MemoryEntry(layer=MemoryLayer.SOUL, key="tone.formal", content="yes"))
        store.write("a", MemoryEntry(layer=MemoryLayer.SOUL, key="tone.casual", content="no"))
        store.write("a", MemoryEntry(layer=MemoryLayer.SOUL, key="style.concise", content="yes"))

        results = store.list_entries("a", MemoryLayer.SOUL, prefix="tone.")
        assert len(results) == 2

    def test_list_entries_limit(self):
        store = InMemoryStore()
        for i in range(10):
            store.write("a", MemoryEntry(layer=MemoryLayer.DIARY, key=f"d{i}", content=f"v{i}"))

        results = store.list_entries("a", MemoryLayer.DIARY, limit=3)
        assert len(results) == 3

    def test_delete(self):
        store = InMemoryStore()
        store.write("a", MemoryEntry(layer=MemoryLayer.MEMORY, key="k", content="v"))
        assert store.delete("a", MemoryLayer.MEMORY, "k") is True
        assert store.read("a", MemoryLayer.MEMORY, "k") is None

    def test_delete_nonexistent(self):
        store = InMemoryStore()
        assert store.delete("a", MemoryLayer.MEMORY, "missing") is False

    def test_expire_removes_stale(self):
        store = InMemoryStore()
        store.write("a", MemoryEntry(
            layer=MemoryLayer.MEMORY, key="fresh", content="v", ttl=3600,
        ))
        store.write("a", MemoryEntry(
            layer=MemoryLayer.MEMORY, key="stale", content="v",
            timestamp=time.time() - 100, ttl=10,
        ))
        removed = store.expire("a")
        assert removed == 1
        assert store.read("a", MemoryLayer.MEMORY, "fresh") is not None

    def test_protocol_compliance(self):
        assert isinstance(InMemoryStore(), MemoryStore)


# ---------------------------------------------------------------------------
# IdentityLoader Tests
# ---------------------------------------------------------------------------


class TestIdentityLoader:
    def test_load_from_dict(self):
        store = InMemoryStore()
        loader = IdentityLoader()
        data = {"name": "TestAgent", "role": "assistant", "constraints": ["be polite"]}
        count = loader.load_from_dict("agent-1", data, store)
        assert count == 3
        entry = store.read("agent-1", MemoryLayer.IDENTITY, "name")
        assert entry is not None
        assert entry.content == "TestAgent"

    def test_load_from_dict_serializes_non_string(self):
        store = InMemoryStore()
        loader = IdentityLoader()
        data = {"constraints": ["a", "b"]}
        loader.load_from_dict("a", data, store)
        entry = store.read("a", MemoryLayer.IDENTITY, "constraints")
        assert entry is not None
        assert json.loads(entry.content) == ["a", "b"]

    def test_load_from_json(self):
        store = InMemoryStore()
        loader = IdentityLoader()
        json_str = '{"name": "Bot", "version": "1.0"}'
        count = loader.load_from_json("a", json_str, store)
        assert count == 2

    def test_load_from_json_invalid(self):
        store = InMemoryStore()
        loader = IdentityLoader()
        with pytest.raises(MemoryError, match="Invalid JSON"):
            loader.load_from_json("a", "not json{", store)

    def test_load_from_json_not_object(self):
        store = InMemoryStore()
        loader = IdentityLoader()
        with pytest.raises(MemoryError, match="must be a top-level object"):
            loader.load_from_json("a", '["array"]', store)

    def test_identity_entries_never_expire(self):
        store = InMemoryStore()
        loader = IdentityLoader()
        loader.load_from_dict("a", {"name": "X"}, store)
        entry = store.read("a", MemoryLayer.IDENTITY, "name")
        assert entry is not None
        assert entry.ttl == 0
        assert entry.is_expired is False


# ---------------------------------------------------------------------------
# SoulManager Tests
# ---------------------------------------------------------------------------


class TestSoulManager:
    def test_set_and_get_trait(self):
        store = InMemoryStore()
        soul = SoulManager(store)
        soul.set_trait("a", "tone", "formal")
        assert soul.get_trait("a", "tone") == "formal"

    def test_get_trait_nonexistent(self):
        store = InMemoryStore()
        soul = SoulManager(store)
        assert soul.get_trait("a", "missing") is None

    def test_list_traits(self):
        store = InMemoryStore()
        soul = SoulManager(store)
        soul.set_trait("a", "tone", "formal")
        soul.set_trait("a", "style", "concise")
        traits = soul.list_traits("a")
        assert traits == {"tone": "formal", "style": "concise"}

    def test_list_traits_with_prefix(self):
        store = InMemoryStore()
        soul = SoulManager(store)
        soul.set_trait("a", "lang.en", "yes")
        soul.set_trait("a", "lang.zh", "yes")
        soul.set_trait("a", "tone", "casual")
        traits = soul.list_traits("a", prefix="lang.")
        assert len(traits) == 2

    def test_delete_trait(self):
        store = InMemoryStore()
        soul = SoulManager(store)
        soul.set_trait("a", "tone", "formal")
        assert soul.delete_trait("a", "tone") is True
        assert soul.get_trait("a", "tone") is None

    def test_delete_trait_nonexistent(self):
        store = InMemoryStore()
        soul = SoulManager(store)
        assert soul.delete_trait("a", "missing") is False

    def test_bulk_set(self):
        store = InMemoryStore()
        soul = SoulManager(store)
        count = soul.bulk_set("a", {"tone": "casual", "humor": "high", "verbosity": "low"})
        assert count == 3
        assert soul.get_trait("a", "humor") == "high"

    def test_set_trait_with_metadata(self):
        store = InMemoryStore()
        soul = SoulManager(store)
        soul.set_trait("a", "tone", "formal", metadata={"source": "user_config"})
        entry = store.read("a", MemoryLayer.SOUL, "tone")
        assert entry is not None
        assert entry.metadata == {"source": "user_config"}


# ---------------------------------------------------------------------------
# MemoryManager Tests — Basic Operations
# ---------------------------------------------------------------------------


class TestMemoryManagerBasic:
    def test_write_and_read(self):
        mgr = MemoryManager(InMemoryStore())
        entry = mgr.write_to_layer("a", MemoryLayer.DIARY, "d1", "had a conversation")
        assert entry.layer == MemoryLayer.DIARY
        assert entry.key == "d1"
        read_back = mgr.read_from_layer("a", MemoryLayer.DIARY, "d1")
        assert read_back is not None
        assert read_back.content == "had a conversation"

    def test_list_layer(self):
        mgr = MemoryManager(InMemoryStore())
        mgr.write_to_layer("a", MemoryLayer.MEMORY, "k1", "v1")
        mgr.write_to_layer("a", MemoryLayer.MEMORY, "k2", "v2")
        mgr.write_to_layer("a", MemoryLayer.DIARY, "d1", "event")
        entries = mgr.list_layer("a", MemoryLayer.MEMORY)
        assert len(entries) == 2

    def test_remember_and_recall(self):
        mgr = MemoryManager(InMemoryStore())
        mgr.remember("a", "user_name", "Alice", ttl=60)
        assert mgr.recall("a", "user_name") == "Alice"

    def test_recall_nonexistent(self):
        mgr = MemoryManager(InMemoryStore())
        assert mgr.recall("a", "missing") is None

    def test_append_diary(self):
        mgr = MemoryManager(InMemoryStore())
        entry = mgr.append_diary("a", "user asked about weather")
        assert entry.layer == MemoryLayer.DIARY
        assert "diary_" in entry.key

    def test_append_diary_with_key(self):
        mgr = MemoryManager(InMemoryStore())
        entry = mgr.append_diary("a", "content", key="custom_key")
        assert entry.key == "custom_key"

    def test_soul_manager_accessible(self):
        mgr = MemoryManager(InMemoryStore())
        mgr.soul.set_trait("a", "tone", "warm")
        assert mgr.soul.get_trait("a", "tone") == "warm"

    def test_identity_loader_accessible(self):
        store = InMemoryStore()
        mgr = MemoryManager(store)
        mgr.identity_loader.load_from_dict("a", {"name": "Bot"}, store)
        entry = mgr.read_from_layer("a", MemoryLayer.IDENTITY, "name")
        assert entry is not None
        assert entry.content == "Bot"


# ---------------------------------------------------------------------------
# MemoryManager Tests — TTL & GC
# ---------------------------------------------------------------------------


class TestMemoryManagerTTL:
    def test_write_with_ttl(self):
        mgr = MemoryManager(InMemoryStore())
        entry = mgr.write_to_layer("a", MemoryLayer.MEMORY, "temp", "val", ttl=5)
        assert entry.ttl == 5

    def test_gc_removes_expired(self):
        store = InMemoryStore()
        mgr = MemoryManager(store)
        # Write a stale entry directly
        stale = MemoryEntry(
            layer=MemoryLayer.MEMORY, key="old", content="v",
            timestamp=time.time() - 100, ttl=10,
        )
        store.write("a", stale)
        mgr.write_to_layer("a", MemoryLayer.MEMORY, "fresh", "v", ttl=3600)

        removed = mgr.gc("a")
        assert removed == 1
        assert mgr.recall("a", "fresh") == "v"

    def test_gc_no_expired(self):
        mgr = MemoryManager(InMemoryStore())
        mgr.remember("a", "k", "v", ttl=3600)
        assert mgr.gc("a") == 0


# ---------------------------------------------------------------------------
# MemoryManager Tests — Semantic Search
# ---------------------------------------------------------------------------


class TestMemoryManagerSearch:
    def test_semantic_search_requires_embedder(self):
        mgr = MemoryManager(InMemoryStore())
        with pytest.raises(MemoryError, match="No EmbeddingProvider"):
            mgr.semantic_search("a", "hello")

    def test_semantic_search_returns_results(self):
        mgr = MemoryManager(InMemoryStore(), embedding_provider=FakeEmbedder())
        mgr.append_diary("a", "the cat sat on the mat", key="d1")
        mgr.append_diary("a", "python programming language", key="d2")
        mgr.append_diary("a", "the dog ran in the park", key="d3")

        results = mgr.semantic_search("a", "cat mat", top_k=2)
        assert len(results) <= 2
        assert all(isinstance(r, SearchResult) for r in results)
        assert all(r.score > 0 for r in results)

    def test_semantic_search_respects_top_k(self):
        mgr = MemoryManager(InMemoryStore(), embedding_provider=FakeEmbedder())
        for i in range(10):
            mgr.append_diary("a", f"entry number {i}", key=f"d{i}")

        results = mgr.semantic_search("a", "entry", top_k=3)
        assert len(results) == 3

    def test_semantic_search_layer_filter(self):
        mgr = MemoryManager(InMemoryStore(), embedding_provider=FakeEmbedder())
        mgr.write_to_layer("a", MemoryLayer.DIARY, "d1", "diary content")
        mgr.write_to_layer("a", MemoryLayer.MEMORY, "m1", "memory content")

        # Search only DIARY
        results = mgr.semantic_search("a", "content", layers=[MemoryLayer.DIARY])
        assert all(r.source_layer == MemoryLayer.DIARY for r in results)

    def test_embedding_ref_set_for_searchable_layers(self):
        mgr = MemoryManager(InMemoryStore(), embedding_provider=FakeEmbedder())
        entry = mgr.write_to_layer("a", MemoryLayer.DIARY, "d1", "content")
        assert entry.embedding_ref is not None

    def test_embedding_ref_not_set_without_embedder(self):
        mgr = MemoryManager(InMemoryStore())
        entry = mgr.write_to_layer("a", MemoryLayer.DIARY, "d1", "content")
        assert entry.embedding_ref is None


# ---------------------------------------------------------------------------
# Protocol Compliance Tests
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    def test_in_memory_store_satisfies_protocol(self):
        assert isinstance(InMemoryStore(), MemoryStore)

    def test_fake_embedder_satisfies_protocol(self):
        assert isinstance(FakeEmbedder(), EmbeddingProvider)
