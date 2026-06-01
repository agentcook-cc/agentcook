"""Model routing layer — fallback / cost-based / quality-first model selection.

Provides a declarative ``ModelConfig`` registry and a ``ModelRouter`` that
selects the best available model according to a configurable ``RoutingPolicy``.
Supports fallback-on-error for resilient multi-provider deployments.

Design:
- stdlib-only (no vendor SDK imports).
- ``ModelAvailabilityChecker`` Protocol — injected health probe, so the
  router never hard-binds to a specific monitoring stack.
- Thread-safe round-robin via simple counter (no asyncio lock needed for
  the stateless selection path; state is atomic int increment).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

from agentcook_core.langfuse_hook import get_langfuse_hook
from agentcook_core.tracing import get_tracer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Value Types
# ---------------------------------------------------------------------------


class RoutingPolicy(str, Enum):
    """Strategy used by ``ModelRouter`` to pick the next model."""

    COST_OPTIMIZED = "cost_optimized"
    QUALITY_FIRST = "quality_first"
    ROUND_ROBIN = "round_robin"
    FALLBACK_CHAIN = "fallback_chain"


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """Declarative model descriptor registered with :class:`ModelRegistry`.

    Attributes:
        name: Vendor-qualified model id (e.g. ``gpt-4o``).
        provider: Provider key (``openai`` / ``anthropic`` / ``qwen``).
        cost_per_1k: USD cost per 1 000 output tokens (used by cost routing).
        max_tokens: Maximum context window tokens.
        quality_score: Abstract quality rank [0..100] (higher = better).
        fallback_order: Priority in fallback chain (lower = tried first).
        tags: Arbitrary labels for filtering (e.g. ``["vision", "code"]``).
        enabled: Soft toggle; disabled models are invisible to the router.
    """

    name: str
    provider: str
    cost_per_1k: float = 0.0
    max_tokens: int = 4096
    quality_score: int = 50
    fallback_order: int = 0
    tags: frozenset[str] = field(default_factory=frozenset)
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class RoutingResult:
    """Outcome of a single :meth:`ModelRouter.select` call."""

    model: ModelConfig
    reason: str
    alternatives_tried: tuple[str, ...] = ()


class ModelRouterError(Exception):
    """Raised when no model can satisfy the routing request."""


# ---------------------------------------------------------------------------
# Protocols (injectable)
# ---------------------------------------------------------------------------


@runtime_checkable
class ModelAvailabilityChecker(Protocol):
    """Injected probe — lets the router check if a model endpoint is live."""

    def is_available(self, model_name: str) -> bool:
        """Return True if the model is reachable / healthy."""
        ...


class _AlwaysAvailable:
    """Default availability — optimistic, all models considered available."""

    def is_available(self, model_name: str) -> bool:  # noqa: ARG002
        return True


# ---------------------------------------------------------------------------
# ModelRegistry
# ---------------------------------------------------------------------------


class ModelRegistry:
    """Central registry for all known model configs.

    Thread-safe for reads; writes (register/unregister) should be done
    during application startup before concurrent routing begins.
    """

    def __init__(self) -> None:
        self._models: dict[str, ModelConfig] = {}

    def register(self, config: ModelConfig) -> None:
        """Register a model. Overwrites if name already exists."""
        self._models[config.name] = config
        logger.debug("Registered model: %s (provider=%s)", config.name, config.provider)

    def unregister(self, name: str) -> ModelConfig | None:
        """Remove and return a model by name; None if absent."""
        return self._models.pop(name, None)

    def get(self, name: str) -> ModelConfig | None:
        """Look up a model by name."""
        return self._models.get(name)

    def list_enabled(self, *, provider: str | None = None, tag: str | None = None) -> list[ModelConfig]:
        """Return enabled models, optionally filtered by provider/tag."""
        result: list[ModelConfig] = []
        for model in self._models.values():
            if not model.enabled:
                continue
            if provider and model.provider != provider:
                continue
            if tag and tag not in model.tags:
                continue
            result.append(model)
        return result

    @property
    def count(self) -> int:
        return len(self._models)

    def clear(self) -> None:
        self._models.clear()


# ---------------------------------------------------------------------------
# ModelRouter
# ---------------------------------------------------------------------------


class ModelRouter:
    """Select the best model according to *policy* and availability.

    Args:
        registry: Source of truth for known models.
        policy: Default routing strategy.
        checker: Injected availability probe (defaults to always-available).
    """

    def __init__(
        self,
        registry: ModelRegistry,
        *,
        policy: RoutingPolicy = RoutingPolicy.FALLBACK_CHAIN,
        checker: ModelAvailabilityChecker | None = None,
    ) -> None:
        self._registry = registry
        self._policy = policy
        self._checker: ModelAvailabilityChecker = checker or _AlwaysAvailable()
        self._round_robin_counter: int = 0

    @property
    def policy(self) -> RoutingPolicy:
        return self._policy

    def select(
        self,
        *,
        policy: RoutingPolicy | None = None,
        provider: str | None = None,
        tag: str | None = None,
        exclude: Sequence[str] | None = None,
    ) -> RoutingResult:
        """Pick the next model to use.

        Args:
            policy: Override the router's default policy for this call.
            provider: Restrict to a specific provider.
            tag: Restrict to models having this tag.
            exclude: Model names to skip (e.g. after a failed attempt).

        Raises:
            ModelRouterError: If no eligible model is available.
        """
        active_policy = policy or self._policy
        exclude_set = set(exclude) if exclude else set()

        with get_tracer().start_span(
            "model.select",
            attributes={
                "agentcook.routing.policy": active_policy.value,
                "agentcook.routing.provider_filter": provider or "",
                "agentcook.routing.tag_filter": tag or "",
                "agentcook.routing.excluded_count": len(exclude_set),
            },
        ) as span:
            candidates = [
                m
                for m in self._registry.list_enabled(provider=provider, tag=tag)
                if m.name not in exclude_set
            ]

            if not candidates:
                raise ModelRouterError("No eligible models found in registry")

            # Filter by availability
            available = [m for m in candidates if self._checker.is_available(m.name)]
            tried_unavailable = tuple(
                m.name for m in candidates if m.name not in {a.name for a in available}
            )

            if not available:
                raise ModelRouterError(
                    f"All candidate models unavailable: {[m.name for m in candidates]}"
                )

            selected = self._apply_policy(available, active_policy)
            span.set_attribute("agentcook.model.name", selected.name)
            span.set_attribute("agentcook.model.provider", selected.provider)

            # Lightweight Langfuse event — records that this model was
            # picked for a routing decision. Real prompt/completion/token
            # observation lives in the provider's chat() call (where the
            # actual LLM round-trip happens). Telemetry is best-effort:
            # any hook exception is swallowed to keep routing resilient.
            try:
                get_langfuse_hook().observe_model_call(
                    model=selected.name,
                    provider=selected.provider,
                    metadata={
                        "event": "model.selected",
                        "policy": active_policy.value,
                        "alternatives_tried": list(tried_unavailable),
                    },
                )
            except Exception:  # noqa: BLE001
                logger.debug("langfuse hook failed for model.selected", exc_info=True)

            return RoutingResult(
                model=selected,
                reason=f"policy={active_policy.value}",
                alternatives_tried=tried_unavailable,
            )

    def select_with_fallback(
        self,
        *,
        provider: str | None = None,
        tag: str | None = None,
        failed_models: Sequence[str] | None = None,
    ) -> RoutingResult:
        """Convenience: select using fallback_chain, excluding already-failed models."""
        return self.select(
            policy=RoutingPolicy.FALLBACK_CHAIN,
            provider=provider,
            tag=tag,
            exclude=failed_models,
        )

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _apply_policy(self, models: list[ModelConfig], policy: RoutingPolicy) -> ModelConfig:
        if policy == RoutingPolicy.COST_OPTIMIZED:
            return min(models, key=lambda m: m.cost_per_1k)

        if policy == RoutingPolicy.QUALITY_FIRST:
            return max(models, key=lambda m: m.quality_score)

        if policy == RoutingPolicy.ROUND_ROBIN:
            idx = self._round_robin_counter % len(models)
            self._round_robin_counter += 1
            # Sort by name for determinism
            sorted_models = sorted(models, key=lambda m: m.name)
            return sorted_models[idx]

        # FALLBACK_CHAIN (default)
        return min(models, key=lambda m: m.fallback_order)


__all__ = [
    "ModelAvailabilityChecker",
    "ModelConfig",
    "ModelRegistry",
    "ModelRouter",
    "ModelRouterError",
    "RoutingPolicy",
    "RoutingResult",
]
