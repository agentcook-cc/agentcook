"""Phase 6 backlog #20: Cloudflare Turnstile verifier for /chat/stream.

The chat endpoint is the second target of the Turnstile / rate-limit
cascade (backlog #11) — the first target was Java login (Day 62
c3eeb10) and the third was the React widget (Day 62 6762ce2). This
module closes the loop so abusive traffic to /api/v1/chat/stream gets
challenged the same way login does.

Three resolution modes, picked in order:

  1. dev_short_circuit=True (or no worker_url + no cloudflare_secret)
     → verified=True / reason="dev_short_circuit"
     Mirrors the Java verifier's dev-mode short-circuit so Phase 3
     dev login + every existing test path keeps running without
     touching Cloudflare.
  2. worker_url set
     → POST {token, remoteIp} to the C-owned Cloudflare Worker
     (Day 62 0bd6ee1, deployed once Day 68 wrangler runs). Worker
     verification at the edge is the production path: ~50ms vs ~200ms
     for a direct siteverify, and the worker can reject obviously bad
     tokens before the request reaches the Python pod.
  3. cloudflare_secret set, worker_url unset
     → POST directly to https://challenges.cloudflare.com/turnstile/v0/siteverify
     Same semantics as the worker, used when the worker isn't
     deployed yet but a secret is configured for end-to-end tests.

Fail-closed: any 5xx / timeout / JSON decode error returns
verified=False with reason="worker_unavailable". This matches the
Day 62 Java TurnstileVerifier choice — letting unverified traffic
through during a Cloudflare outage defeats the gate's purpose.

The TurnstileDecision dataclass carries error_codes pass-through so
the route layer can surface Cloudflare-specific failure reasons
(`invalid-input-response` / `timeout-or-duplicate` / etc) in the 401
body without the route layer having to know the upstream shape.

Test seam: pass a custom httpx.AsyncClient (e.g. one built around
httpx.AsyncBaseTransport in tests/test_turnstile_middleware.py) to
mock the upstream entirely. The verifier never imports the SDK
implicitly, so the tests + the production path use the exact same
codepath.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Env-var defaults (overridable via constructor for tests)
# ---------------------------------------------------------------------------

# Default to the C-owned Worker route. Empty string means "fall back to
# direct siteverify or dev short-circuit"; the verifier never crashes
# on a missing env.
DEFAULT_WORKER_URL: str = os.environ.get(
    "AGENTCOOK_TURNSTILE_WORKER_URL", ""
).strip()

DEFAULT_CLOUDFLARE_SECRET: str = os.environ.get(
    "AGENTCOOK_TURNSTILE_SECRET", ""
).strip()


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("true", "1", "yes")


# Default ON — every existing test + dev workflow runs with no
# Cloudflare account. Prod sets this to false (or unsets) once
# wrangler deploy lands.
DEFAULT_DEV_SHORT_CIRCUIT: bool = _env_truthy("AGENTCOOK_TURNSTILE_DEV_SHORT_CIRCUIT")
if "AGENTCOOK_TURNSTILE_DEV_SHORT_CIRCUIT" not in os.environ:
    DEFAULT_DEV_SHORT_CIRCUIT = True


SITEVERIFY_URL: str = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


# ---------------------------------------------------------------------------
# Decision value type
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TurnstileDecision:
    """Outcome of one TurnstileVerifier.verify() call.

    ``verified`` is the only boolean callers should branch on.
    ``reason`` + ``error_codes`` exist for telemetry / 401 response
    bodies / 调试 logs — never as gate conditions.
    """

    verified: bool
    reason: str  # "verified" | "dev_short_circuit" | "missing_token" | "worker_unavailable" | "cloudflare_rejected"
    error_codes: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------


class TurnstileVerifier:
    """Verify Cloudflare Turnstile tokens at chat-stream entry.

    Constructor parameters mirror the Day 62 Java
    `cc.agentcook.api.auth.TurnstileVerifier` so the two implementations
    stay obviously paired. Tests pass an httpx.AsyncClient with a
    custom AsyncBaseTransport to avoid any real network call.
    """

    def __init__(
        self,
        *,
        worker_url: str | None = None,
        cloudflare_secret: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        dev_short_circuit: bool | None = None,
        timeout_seconds: float = 3.0,
    ) -> None:
        self._worker_url = (worker_url or "").strip()
        self._cloudflare_secret = (cloudflare_secret or "").strip()
        self._http_client = http_client
        self._owns_client = http_client is None
        # Explicit constructor override > env default. We can't just `or`
        # because False is a valid intentional value.
        if dev_short_circuit is None:
            self._dev_short_circuit = DEFAULT_DEV_SHORT_CIRCUIT
        else:
            self._dev_short_circuit = dev_short_circuit
        self._timeout = timeout_seconds

    async def verify(
        self,
        token: str | None,
        *,
        remote_ip: str | None = None,
    ) -> TurnstileDecision:
        """Return a TurnstileDecision for one user request."""
        # Mode 1: dev short-circuit OR no upstream configured at all
        if self._dev_short_circuit or (
            not self._worker_url and not self._cloudflare_secret
        ):
            return TurnstileDecision(
                verified=True, reason="dev_short_circuit"
            )

        # Mode 2/3 require a token
        if not token or not token.strip():
            return TurnstileDecision(
                verified=False, reason="missing_token"
            )

        if self._worker_url:
            return await self._verify_via_worker(token, remote_ip)
        return await self._verify_via_siteverify(token, remote_ip)

    # -- internal -----------------------------------------------------------

    async def _verify_via_worker(
        self,
        token: str,
        remote_ip: str | None,
    ) -> TurnstileDecision:
        payload: dict[str, Any] = {"token": token}
        if remote_ip:
            payload["remoteIp"] = remote_ip
        return await self._call_upstream(self._worker_url, payload, json_body=True)

    async def _verify_via_siteverify(
        self,
        token: str,
        remote_ip: str | None,
    ) -> TurnstileDecision:
        # Cloudflare siteverify is form-encoded (`response` is the
        # token; `secret` is the site secret). Keep the same Decision
        # shape so callers don't need to know which mode ran.
        data: dict[str, str] = {
            "secret": self._cloudflare_secret,
            "response": token,
        }
        if remote_ip:
            data["remoteip"] = remote_ip
        return await self._call_upstream(SITEVERIFY_URL, data, json_body=False)

    async def _call_upstream(
        self,
        url: str,
        body: dict[str, Any],
        *,
        json_body: bool,
    ) -> TurnstileDecision:
        try:
            client = self._http_client or httpx.AsyncClient(timeout=self._timeout)
            try:
                if json_body:
                    resp = await client.post(url, json=body)
                else:
                    resp = await client.post(url, data=body)
            finally:
                if self._owns_client:
                    await client.aclose()
        except (httpx.HTTPError, OSError) as exc:
            logger.warning(
                "Turnstile upstream %s unreachable (%s) — fail-closed",
                url,
                exc,
            )
            return TurnstileDecision(
                verified=False, reason="worker_unavailable"
            )

        if resp.status_code >= 500:
            logger.warning(
                "Turnstile upstream %s returned %s — fail-closed",
                url,
                resp.status_code,
            )
            return TurnstileDecision(
                verified=False, reason="worker_unavailable"
            )

        try:
            payload = resp.json()
        except (ValueError, httpx.DecodingError):
            logger.warning(
                "Turnstile upstream %s returned non-JSON — fail-closed",
                url,
            )
            return TurnstileDecision(
                verified=False, reason="worker_unavailable"
            )

        success = bool(payload.get("success"))
        # Cloudflare uses both `error-codes` (siteverify) and
        # `error_codes` (Worker). Accept either spelling.
        raw_codes = payload.get("error-codes") or payload.get("error_codes") or ()
        if isinstance(raw_codes, str):
            error_codes: tuple[str, ...] = (raw_codes,)
        else:
            error_codes = tuple(str(c) for c in raw_codes)

        if success:
            return TurnstileDecision(verified=True, reason="verified")
        return TurnstileDecision(
            verified=False,
            reason="cloudflare_rejected",
            error_codes=error_codes,
        )


# ---------------------------------------------------------------------------
# Lazy singleton (production path through chat.py)
# ---------------------------------------------------------------------------

_verifier_cache: TurnstileVerifier | None = None


def get_turnstile_verifier() -> TurnstileVerifier:
    """Lazy singleton wired from env. Tests inject their own instance."""
    global _verifier_cache
    if _verifier_cache is None:
        _verifier_cache = TurnstileVerifier(
            worker_url=DEFAULT_WORKER_URL or None,
            cloudflare_secret=DEFAULT_CLOUDFLARE_SECRET or None,
        )
    return _verifier_cache


def reset_turnstile_verifier() -> None:
    """Reset singleton — used by tests to avoid cache bleed."""
    global _verifier_cache
    _verifier_cache = None


__all__ = [
    "DEFAULT_CLOUDFLARE_SECRET",
    "DEFAULT_DEV_SHORT_CIRCUIT",
    "DEFAULT_WORKER_URL",
    "SITEVERIFY_URL",
    "TurnstileDecision",
    "TurnstileVerifier",
    "get_turnstile_verifier",
    "reset_turnstile_verifier",
]
