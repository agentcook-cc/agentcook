"""FastAPI middleware + cross-cutting dependencies for agentcook runtime.

Exports:
  - ADR-018 quota resolver (Day 56)
  - Phase 6 backlog #20 Cloudflare Turnstile verifier (Buffer Day 68)

Future middleware (rate limit / request signing / etc) lands here
following the same shape: sync construction, async resolution,
dataclass decisions, env-var defaults overridable via constructor
for tests.
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
from agentcook_app.middleware.turnstile import (
    DEFAULT_CLOUDFLARE_SECRET,
    DEFAULT_DEV_SHORT_CIRCUIT,
    DEFAULT_WORKER_URL,
    SITEVERIFY_URL,
    TurnstileDecision,
    TurnstileVerifier,
    get_turnstile_verifier,
    reset_turnstile_verifier,
)

__all__ = [
    "DEFAULT_CLOUDFLARE_SECRET",
    "DEFAULT_DEV_SHORT_CIRCUIT",
    "DEFAULT_QUOTA",
    "DEFAULT_WORKER_URL",
    "FALLBACK_MODEL",
    "FALLBACK_PROVIDER",
    "PRIMARY_MODEL",
    "PRIMARY_PROVIDER",
    "QuotaDecision",
    "QuotaResolver",
    "SITEVERIFY_URL",
    "TurnstileDecision",
    "TurnstileVerifier",
    "get_turnstile_verifier",
    "reset_turnstile_verifier",
]
