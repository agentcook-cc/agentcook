"""FastAPI middleware + cross-cutting dependencies for agentcook runtime.

Currently exports the ADR-018 quota resolver. Future middleware (rate
limit / request signing / etc) lands here following the same shape:
sync construction, async resolution, dataclass decisions, env-var
defaults overridable via constructor for tests.
"""

from __future__ import annotations

from agentcook_app.middleware.quota import (
    DEFAULT_QUOTA,
    FALLBACK_MODEL,
    FALLBACK_PROVIDER,
    PRIMARY_MODEL,
    PRIMARY_PROVIDER,
    QuotaDecision,
    QuotaResolver,
)

__all__ = [
    "DEFAULT_QUOTA",
    "FALLBACK_MODEL",
    "FALLBACK_PROVIDER",
    "PRIMARY_MODEL",
    "PRIMARY_PROVIDER",
    "QuotaDecision",
    "QuotaResolver",
]
