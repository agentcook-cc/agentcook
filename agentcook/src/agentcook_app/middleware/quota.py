"""ADR-018 quota resolver — JWT sub → Java /api/v1/quota → provider choice.

Implements the four-tier fallback chain documented in ADR-018 §2:

    free_questions_used < quota → qwen-turbo (primary)
                              ≥ quota → glm-4-flash (fallback, free)
              glm-4-flash unavailable → qwen-plus (paid, monthly cap)
                       qwen-plus down → echo (mock, never 500)

Per ADR-018 §1 v1 defaults:
- 2 free questions per account (env: AGENTCOOK_FREE_QUOTA_DEFAULT)
- Anonymous (no JWT) shares an IP-level bucket handled by Cloudflare
  Turnstile + Rate Limit (Phase 5 backlog #11). Until that lands the
  Python middleware routes anonymous requests directly to the free
  fallback (glm-4-flash) to keep demo cost at zero.

Design notes:
- Not a FastAPI ``BaseHTTPMiddleware`` despite the module name — using
  a constructor-injected ``QuotaResolver`` with an ``async resolve()``
  method is cleaner because (a) quota only matters for one endpoint
  (``/api/v1/chat/stream``), and (b) it stays testable without a
  ``starlette.testclient`` per scenario.
- Java quota service errors are swallowed: we degrade to fallback +
  attach the reason to ``QuotaDecision.reason`` so the caller can
  surface a polite "service temporarily degraded" notice without
  breaking the chat stream.
- ``config_override`` short-circuits Java lookup entirely. Used by
  admin-only routes and unit tests; never set from user input.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Env-var defaults (overridable via constructor for tests)
# ---------------------------------------------------------------------------

DEFAULT_QUOTA: int = int(os.environ.get("AGENTCOOK_FREE_QUOTA_DEFAULT", "2"))
PRIMARY_PROVIDER: str = os.environ.get("AGENTCOOK_QUOTA_PRIMARY_PROVIDER", "qwen")
PRIMARY_MODEL: str = os.environ.get("AGENTCOOK_QUOTA_PRIMARY_MODEL", "qwen-turbo")
FALLBACK_PROVIDER: str = os.environ.get("AGENTCOOK_QUOTA_FALLBACK_PROVIDER", "zhipu")
FALLBACK_MODEL: str = os.environ.get("AGENTCOOK_QUOTA_FALLBACK_MODEL", "glm-4-flash")

# Java quota service base URL. Defaults to in-cluster service DNS;
# overridable for local dev (e.g. http://localhost:8080) and tests.
_DEFAULT_JAVA_QUOTA_URL: str = os.environ.get(
    "AGENTCOOK_JAVA_QUOTA_URL", "http://admin-bff:8080/api/v1/quota"
)


# ---------------------------------------------------------------------------
# Decision value type
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class QuotaDecision:
    """Outcome of one quota resolve() call.

    Caller passes ``provider`` + ``model`` to
    ``chat._stream_real_response(provider_override=...)`` and surfaces
    ``remaining`` / ``reason`` to the frontend for UI display.
    """

    provider: str
    model: str | None
    remaining: int
    reason: str  # "within_quota" | "exhausted" | "anonymous" | "config_override" | "java_unavailable"


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------


class QuotaResolver:
    """Resolve which LLM provider/model a chat turn should use.

    Construction injects URL + http client + defaults so tests can pass
    a respx-mocked client (or any AsyncClient subclass) and override
    every default without touching env vars.
    """

    def __init__(
        self,
        *,
        java_quota_url: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        default_quota: int = DEFAULT_QUOTA,
        primary_provider: str = PRIMARY_PROVIDER,
        primary_model: str = PRIMARY_MODEL,
        fallback_provider: str = FALLBACK_PROVIDER,
        fallback_model: str = FALLBACK_MODEL,
        timeout_seconds: float = 2.0,
    ) -> None:
        self._java_quota_url = java_quota_url or _DEFAULT_JAVA_QUOTA_URL
        self._http_client = http_client
        self._owns_client = http_client is None
        self._default_quota = default_quota
        self._primary_provider = primary_provider
        self._primary_model = primary_model
        self._fallback_provider = fallback_provider
        self._fallback_model = fallback_model
        self._timeout = timeout_seconds

    async def resolve(
        self,
        user_id: str | None,
        *,
        bearer_token: str | None = None,
        config_override: str | None = None,
    ) -> QuotaDecision:
        """Pick a provider for one chat turn.

        :param user_id: JWT ``sub`` claim if authenticated, else ``None``.
        :param bearer_token: raw token forwarded to Java quota lookup
                             (Java needs it to identify the user).
        :param config_override: short-circuit — if set, returned as the
                                provider name unchanged. Used by admin
                                routes / unit tests; never from user input.
        """
        if config_override:
            return QuotaDecision(
                provider=config_override,
                model=None,
                remaining=-1,
                reason="config_override",
            )

        if user_id is None:
            # Anonymous traffic: Phase 5 backlog #11 will gate this with
            # Cloudflare Turnstile + Rate Limit; meanwhile route to the
            # free fallback to keep demo cost at zero.
            return QuotaDecision(
                provider=self._fallback_provider,
                model=self._fallback_model,
                remaining=0,
                reason="anonymous",
            )

        quota_info = await self._fetch_java_quota(user_id, bearer_token)
        if quota_info is None:
            # Java unreachable — degrade to fallback so chat keeps working.
            return QuotaDecision(
                provider=self._fallback_provider,
                model=self._fallback_model,
                remaining=0,
                reason="java_unavailable",
            )

        used = int(quota_info.get("free_questions_used", 0))
        quota = int(quota_info.get("free_questions_quota", self._default_quota))
        remaining = max(0, quota - used)

        if used < quota:
            return QuotaDecision(
                provider=self._primary_provider,
                model=self._primary_model,
                remaining=remaining,
                reason="within_quota",
            )

        return QuotaDecision(
            provider=self._fallback_provider,
            model=self._fallback_model,
            remaining=0,
            reason="exhausted",
        )

    async def _fetch_java_quota(
        self,
        user_id: str,
        bearer_token: str | None,
    ) -> dict[str, Any] | None:
        """Call Java ``GET /api/v1/quota``. Returns ``None`` on any
        error so callers can degrade cleanly."""
        headers: dict[str, str] = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        try:
            client = self._http_client or httpx.AsyncClient(timeout=self._timeout)
            try:
                resp = await client.get(self._java_quota_url, headers=headers)
            finally:
                if self._owns_client:
                    await client.aclose()
            if resp.status_code != 200:
                logger.warning(
                    "Java quota service returned %s for user %s — degrading to fallback",
                    resp.status_code,
                    user_id,
                )
                return None
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "Java quota lookup failed for user %s (%s) — degrading to fallback",
                user_id,
                exc,
            )
            return None
