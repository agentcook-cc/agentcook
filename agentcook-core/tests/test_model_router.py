"""Unit tests for agentcook_core.model_router module."""

from __future__ import annotations

import pytest
from agentcook_core.model_router import (
    ModelAvailabilityChecker,
    ModelConfig,
    ModelRegistry,
    ModelRouter,
    ModelRouterError,
    RoutingPolicy,
    RoutingResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def gpt4o() -> ModelConfig:
    return ModelConfig(
        name="gpt-4o",
        provider="openai",
        cost_per_1k=0.03,
        max_tokens=128_000,
        quality_score=95,
        fallback_order=0,
        tags=frozenset(["vision", "code"]),
    )


@pytest.fixture
def gpt35() -> ModelConfig:
    return ModelConfig(
        name="gpt-3.5-turbo",
        provider="openai",
        cost_per_1k=0.002,
        max_tokens=16_000,
        quality_score=70,
        fallback_order=1,
    )


@pytest.fixture
def claude() -> ModelConfig:
    return ModelConfig(
        name="claude-3-sonnet",
        provider="anthropic",
        cost_per_1k=0.015,
        max_tokens=200_000,
        quality_score=90,
        fallback_order=2,
        tags=frozenset(["code"]),
    )


@pytest.fixture
def qwen() -> ModelConfig:
    return ModelConfig(
        name="qwen-max",
        provider="qwen",
        cost_per_1k=0.005,
        max_tokens=32_000,
        quality_score=80,
        fallback_order=3,
    )


@pytest.fixture
def registry(gpt4o, gpt35, claude, qwen) -> ModelRegistry:
    reg = ModelRegistry()
    for m in [gpt4o, gpt35, claude, qwen]:
        reg.register(m)
    return reg


# ---------------------------------------------------------------------------
# ModelConfig Tests
# ---------------------------------------------------------------------------


class TestModelConfig:
    def test_frozen_immutable(self, gpt4o: ModelConfig):
        with pytest.raises(AttributeError):
            gpt4o.name = "other"  # type: ignore[misc]

    def test_defaults(self):
        cfg = ModelConfig(name="test", provider="local")
        assert cfg.cost_per_1k == 0.0
        assert cfg.max_tokens == 4096
        assert cfg.quality_score == 50
        assert cfg.fallback_order == 0
        assert cfg.tags == frozenset()
        assert cfg.enabled is True

    def test_tags_frozenset(self, gpt4o: ModelConfig):
        assert "vision" in gpt4o.tags
        assert "code" in gpt4o.tags


# ---------------------------------------------------------------------------
# ModelRegistry Tests
# ---------------------------------------------------------------------------


class TestModelRegistry:
    def test_register_and_get(self, registry: ModelRegistry, gpt4o: ModelConfig):
        assert registry.get("gpt-4o") == gpt4o

    def test_get_nonexistent(self, registry: ModelRegistry):
        assert registry.get("nonexistent") is None

    def test_unregister(self, registry: ModelRegistry):
        removed = registry.unregister("gpt-4o")
        assert removed is not None
        assert removed.name == "gpt-4o"
        assert registry.get("gpt-4o") is None

    def test_unregister_nonexistent(self, registry: ModelRegistry):
        assert registry.unregister("nonexistent") is None

    def test_count(self, registry: ModelRegistry):
        assert registry.count == 4

    def test_list_enabled_all(self, registry: ModelRegistry):
        models = registry.list_enabled()
        assert len(models) == 4

    def test_list_enabled_by_provider(self, registry: ModelRegistry):
        openai_models = registry.list_enabled(provider="openai")
        assert len(openai_models) == 2
        assert all(m.provider == "openai" for m in openai_models)

    def test_list_enabled_by_tag(self, registry: ModelRegistry):
        code_models = registry.list_enabled(tag="code")
        assert len(code_models) == 2
        names = {m.name for m in code_models}
        assert names == {"gpt-4o", "claude-3-sonnet"}

    def test_disabled_model_excluded(self, registry: ModelRegistry):
        disabled = ModelConfig(name="disabled-model", provider="test", enabled=False)
        registry.register(disabled)
        assert registry.count == 5
        assert len(registry.list_enabled()) == 4

    def test_clear(self, registry: ModelRegistry):
        registry.clear()
        assert registry.count == 0

    def test_overwrite_on_register(self, registry: ModelRegistry):
        updated = ModelConfig(name="gpt-4o", provider="openai", cost_per_1k=0.05)
        registry.register(updated)
        assert registry.get("gpt-4o").cost_per_1k == 0.05


# ---------------------------------------------------------------------------
# ModelRouter Tests — Routing Policies
# ---------------------------------------------------------------------------


class TestModelRouterPolicies:
    def test_cost_optimized(self, registry: ModelRegistry):
        router = ModelRouter(registry, policy=RoutingPolicy.COST_OPTIMIZED)
        result = router.select()
        assert result.model.name == "gpt-3.5-turbo"  # cheapest
        assert "cost_optimized" in result.reason

    def test_quality_first(self, registry: ModelRegistry):
        router = ModelRouter(registry, policy=RoutingPolicy.QUALITY_FIRST)
        result = router.select()
        assert result.model.name == "gpt-4o"  # highest quality_score=95

    def test_fallback_chain(self, registry: ModelRegistry):
        router = ModelRouter(registry, policy=RoutingPolicy.FALLBACK_CHAIN)
        result = router.select()
        assert result.model.name == "gpt-4o"  # lowest fallback_order=0

    def test_round_robin_cycles(self, registry: ModelRegistry):
        router = ModelRouter(registry, policy=RoutingPolicy.ROUND_ROBIN)
        selected_names = [router.select().model.name for _ in range(8)]
        # Should cycle through models deterministically
        assert len(set(selected_names)) == 4

    def test_policy_override_per_call(self, registry: ModelRegistry):
        router = ModelRouter(registry, policy=RoutingPolicy.FALLBACK_CHAIN)
        result = router.select(policy=RoutingPolicy.COST_OPTIMIZED)
        assert result.model.name == "gpt-3.5-turbo"


# ---------------------------------------------------------------------------
# ModelRouter Tests — Filtering
# ---------------------------------------------------------------------------


class TestModelRouterFiltering:
    def test_filter_by_provider(self, registry: ModelRegistry):
        router = ModelRouter(registry, policy=RoutingPolicy.COST_OPTIMIZED)
        result = router.select(provider="anthropic")
        assert result.model.provider == "anthropic"

    def test_filter_by_tag(self, registry: ModelRegistry):
        router = ModelRouter(registry, policy=RoutingPolicy.COST_OPTIMIZED)
        result = router.select(tag="vision")
        assert result.model.name == "gpt-4o"  # only model with vision tag

    def test_exclude_models(self, registry: ModelRegistry):
        router = ModelRouter(registry, policy=RoutingPolicy.FALLBACK_CHAIN)
        result = router.select(exclude=["gpt-4o"])
        assert result.model.name == "gpt-3.5-turbo"  # next in fallback_order

    def test_no_eligible_models_raises(self, registry: ModelRegistry):
        router = ModelRouter(registry, policy=RoutingPolicy.FALLBACK_CHAIN)
        with pytest.raises(ModelRouterError, match="No eligible models"):
            router.select(provider="nonexistent")


# ---------------------------------------------------------------------------
# ModelRouter Tests — Availability
# ---------------------------------------------------------------------------


class TestModelRouterAvailability:
    def test_unavailable_model_skipped(self, registry: ModelRegistry):
        class PartialChecker:
            def is_available(self, model_name: str) -> bool:
                return model_name != "gpt-4o"

        router = ModelRouter(registry, policy=RoutingPolicy.FALLBACK_CHAIN, checker=PartialChecker())
        result = router.select()
        assert result.model.name == "gpt-3.5-turbo"
        assert "gpt-4o" in result.alternatives_tried

    def test_all_unavailable_raises(self, registry: ModelRegistry):
        class NoneAvailable:
            def is_available(self, model_name: str) -> bool:
                return False

        router = ModelRouter(registry, policy=RoutingPolicy.FALLBACK_CHAIN, checker=NoneAvailable())
        with pytest.raises(ModelRouterError, match="All candidate models unavailable"):
            router.select()

    def test_checker_protocol_compliance(self):
        class MyChecker:
            def is_available(self, model_name: str) -> bool:
                return True

        assert isinstance(MyChecker(), ModelAvailabilityChecker)


# ---------------------------------------------------------------------------
# ModelRouter Tests — select_with_fallback
# ---------------------------------------------------------------------------


class TestModelRouterFallback:
    def test_select_with_fallback_excludes_failed(self, registry: ModelRegistry):
        router = ModelRouter(registry)
        result = router.select_with_fallback(failed_models=["gpt-4o", "gpt-3.5-turbo"])
        assert result.model.name == "claude-3-sonnet"  # fallback_order=2

    def test_select_with_fallback_provider_filter(self, registry: ModelRegistry):
        router = ModelRouter(registry)
        result = router.select_with_fallback(provider="openai", failed_models=["gpt-4o"])
        assert result.model.name == "gpt-3.5-turbo"


# ---------------------------------------------------------------------------
# RoutingResult Tests
# ---------------------------------------------------------------------------


class TestRoutingResult:
    def test_result_fields(self, registry: ModelRegistry):
        router = ModelRouter(registry)
        result = router.select()
        assert isinstance(result, RoutingResult)
        assert isinstance(result.model, ModelConfig)
        assert isinstance(result.reason, str)
        assert isinstance(result.alternatives_tried, tuple)
