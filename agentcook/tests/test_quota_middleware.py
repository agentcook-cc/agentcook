"""ADR-018 quota middleware tests — 5 scenarios per ADR §Validation.

Resolves the QuotaResolver decision for each combination of (user
identity, Java quota service availability, config override). Java
service is mocked via respx-style monkeypatched httpx.AsyncClient so
no live admin-bff is required.

Scenarios:

1. anonymous user (no JWT)            → fallback (zhipu/glm-4-flash)
2. authenticated within quota          → primary (qwen/qwen-turbo)
3. authenticated exhausted             → fallback (zhipu/glm-4-flash)
4. Java service unavailable            → fallback (graceful degradation)
5. config_override                     → as specified, bypass Java
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from agentcook_app.middleware import (
    DEFAULT_QUOTA,
    FALLBACK_MODEL,
    FALLBACK_PROVIDER,
    PRIMARY_MODEL,
    PRIMARY_PROVIDER,
    QuotaDecision,
    QuotaResolver,
)


# ---------------------------------------------------------------------------
# Mock transport — controls what Java /api/v1/quota returns per test
# ---------------------------------------------------------------------------


class _MockTransport(httpx.AsyncBaseTransport):
    """Minimal AsyncBaseTransport that returns whatever ``handler`` builds."""

    def __init__(self, handler):
        self._handler = handler
        self.calls: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        return self._handler(request)


def _build_client(handler) -> tuple[httpx.AsyncClient, _MockTransport]:
    transport = _MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    return client, transport


def _build_resolver(client: httpx.AsyncClient | None = None) -> QuotaResolver:
    return QuotaResolver(
        java_quota_url="http://test-java/api/v1/quota",
        http_client=client,
        default_quota=2,
        primary_provider="qwen",
        primary_model="qwen-turbo",
        fallback_provider="zhipu",
        fallback_model="glm-4-flash",
        timeout_seconds=1.0,
    )


# ---------------------------------------------------------------------------
# Scenario 1: anonymous user (no JWT)
# ---------------------------------------------------------------------------


class TestAnonymousUser:
    async def test_anonymous_routes_to_fallback(self):
        resolver = _build_resolver()
        decision = await resolver.resolve(user_id=None)
        assert decision.provider == "zhipu"
        assert decision.model == "glm-4-flash"
        assert decision.reason == "anonymous"
        assert decision.remaining == 0

    async def test_anonymous_does_not_call_java(self):
        client, transport = _build_client(
            lambda req: httpx.Response(500, json={})
        )
        resolver = _build_resolver(client=client)
        decision = await resolver.resolve(user_id=None)
        await client.aclose()

        assert decision.reason == "anonymous"
        # Java endpoint must not be hit when caller is anonymous.
        assert transport.calls == []


# ---------------------------------------------------------------------------
# Scenario 2: authenticated within quota
# ---------------------------------------------------------------------------


class TestAuthenticatedWithinQuota:
    async def test_within_quota_routes_to_primary(self):
        client, _ = _build_client(
            lambda req: httpx.Response(
                200,
                json={"free_questions_used": 1, "free_questions_quota": 2},
            )
        )
        resolver = _build_resolver(client=client)
        decision = await resolver.resolve(user_id="usr-001", bearer_token="tok")
        await client.aclose()

        assert decision.provider == "qwen"
        assert decision.model == "qwen-turbo"
        assert decision.remaining == 1
        assert decision.reason == "within_quota"

    async def test_zero_used_returns_full_remaining(self):
        client, _ = _build_client(
            lambda req: httpx.Response(
                200,
                json={"free_questions_used": 0, "free_questions_quota": 2},
            )
        )
        resolver = _build_resolver(client=client)
        decision = await resolver.resolve(user_id="usr-002", bearer_token="tok")
        await client.aclose()

        assert decision.reason == "within_quota"
        assert decision.remaining == 2

    async def test_bearer_token_forwarded_to_java(self):
        client, transport = _build_client(
            lambda req: httpx.Response(
                200,
                json={"free_questions_used": 0, "free_questions_quota": 2},
            )
        )
        resolver = _build_resolver(client=client)
        await resolver.resolve(user_id="usr-003", bearer_token="abc.def.ghi")
        await client.aclose()

        assert len(transport.calls) == 1
        assert transport.calls[0].headers.get("authorization") == "Bearer abc.def.ghi"


# ---------------------------------------------------------------------------
# Scenario 3: authenticated exhausted → fallback
# ---------------------------------------------------------------------------


class TestAuthenticatedExhausted:
    async def test_exhausted_routes_to_fallback(self):
        client, _ = _build_client(
            lambda req: httpx.Response(
                200,
                json={"free_questions_used": 2, "free_questions_quota": 2},
            )
        )
        resolver = _build_resolver(client=client)
        decision = await resolver.resolve(user_id="usr-001", bearer_token="tok")
        await client.aclose()

        assert decision.provider == "zhipu"
        assert decision.model == "glm-4-flash"
        assert decision.remaining == 0
        assert decision.reason == "exhausted"

    async def test_over_quota_clamps_remaining_to_zero(self):
        client, _ = _build_client(
            lambda req: httpx.Response(
                200,
                json={"free_questions_used": 7, "free_questions_quota": 2},
            )
        )
        resolver = _build_resolver(client=client)
        decision = await resolver.resolve(user_id="usr-001", bearer_token="tok")
        await client.aclose()

        # Even when Java reports 7 used / 2 quota (shouldn't happen, but
        # defend against drift), remaining stays clamped at 0.
        assert decision.remaining == 0
        assert decision.reason == "exhausted"


# ---------------------------------------------------------------------------
# Scenario 4: Java service unavailable → graceful fallback
# ---------------------------------------------------------------------------


class TestJavaUnavailable:
    async def test_500_response_degrades_to_fallback(self):
        client, _ = _build_client(
            lambda req: httpx.Response(500, json={"error": "internal"})
        )
        resolver = _build_resolver(client=client)
        decision = await resolver.resolve(user_id="usr-001", bearer_token="tok")
        await client.aclose()

        assert decision.provider == "zhipu"
        assert decision.model == "glm-4-flash"
        assert decision.reason == "java_unavailable"

    async def test_connect_error_degrades_to_fallback(self):
        def _raise(req: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("admin-bff unreachable", request=req)

        client, _ = _build_client(_raise)
        resolver = _build_resolver(client=client)
        decision = await resolver.resolve(user_id="usr-001", bearer_token="tok")
        await client.aclose()

        assert decision.provider == "zhipu"
        assert decision.reason == "java_unavailable"

    async def test_malformed_json_degrades_to_fallback(self):
        client, _ = _build_client(
            lambda req: httpx.Response(
                200, content=b"not json at all", headers={"content-type": "text/plain"}
            )
        )
        resolver = _build_resolver(client=client)
        decision = await resolver.resolve(user_id="usr-001", bearer_token="tok")
        await client.aclose()

        assert decision.reason == "java_unavailable"


# ---------------------------------------------------------------------------
# Scenario 5: config_override short-circuits Java lookup
# ---------------------------------------------------------------------------


class TestConfigOverride:
    async def test_override_bypasses_java(self):
        client, transport = _build_client(
            lambda req: httpx.Response(500, json={})
        )
        resolver = _build_resolver(client=client)
        decision = await resolver.resolve(
            user_id="usr-001",
            bearer_token="tok",
            config_override="echo",
        )
        await client.aclose()

        assert decision.provider == "echo"
        assert decision.reason == "config_override"
        # Java endpoint must NOT be hit when config_override is set.
        assert transport.calls == []

    async def test_override_works_for_anonymous_too(self):
        resolver = _build_resolver()
        decision = await resolver.resolve(
            user_id=None,
            config_override="qwen",
        )
        assert decision.provider == "qwen"
        assert decision.reason == "config_override"


# ---------------------------------------------------------------------------
# Module-level defaults sanity check (env vars)
# ---------------------------------------------------------------------------


class TestModuleDefaults:
    def test_default_quota_is_two(self):
        assert DEFAULT_QUOTA == 2

    def test_primary_is_qwen_turbo(self):
        assert PRIMARY_PROVIDER == "qwen"
        assert PRIMARY_MODEL == "qwen-turbo"

    def test_fallback_is_zhipu_glm4_flash(self):
        assert FALLBACK_PROVIDER == "zhipu"
        assert FALLBACK_MODEL == "glm-4-flash"

    def test_decision_is_frozen(self):
        d = QuotaDecision(
            provider="qwen", model="qwen-turbo", remaining=1, reason="within_quota"
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            d.provider = "other"  # type: ignore[misc]
