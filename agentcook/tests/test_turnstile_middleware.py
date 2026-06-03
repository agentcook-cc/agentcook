"""Phase 6 backlog #20 — TurnstileVerifier tests (Buffer Day 68).

Covers all 3 resolution modes + the 5 outcome reasons + the lazy
singleton + the dev-short-circuit env default. Java service is mocked
via an httpx.AsyncBaseTransport so no live Cloudflare Worker / no
live siteverify endpoint is required.

Test fixtures mirror test_quota_middleware.py's `_MockTransport`
pattern (Day 56) so the two middleware modules read the same way.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from agentcook_app.middleware import (
    DEFAULT_DEV_SHORT_CIRCUIT,
    SITEVERIFY_URL,
    TurnstileDecision,
    TurnstileVerifier,
    get_turnstile_verifier,
    reset_turnstile_verifier,
)


# ---------------------------------------------------------------------------
# Mock transport (same shape as test_quota_middleware.py)
# ---------------------------------------------------------------------------


class _MockTransport(httpx.AsyncBaseTransport):
    """Returns whatever ``handler`` builds, records every request."""

    def __init__(self, handler):
        self._handler = handler
        self.calls: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        return self._handler(request)


def _build_client(handler) -> tuple[httpx.AsyncClient, _MockTransport]:
    transport = _MockTransport(handler)
    return httpx.AsyncClient(transport=transport), transport


def _build_worker_verifier(
    client: httpx.AsyncClient | None = None,
    *,
    dev_short_circuit: bool = False,
) -> TurnstileVerifier:
    return TurnstileVerifier(
        worker_url="https://turnstile.test/verify",
        http_client=client,
        dev_short_circuit=dev_short_circuit,
        timeout_seconds=1.0,
    )


def _build_siteverify_verifier(
    client: httpx.AsyncClient | None = None,
) -> TurnstileVerifier:
    return TurnstileVerifier(
        cloudflare_secret="dev-secret",
        http_client=client,
        dev_short_circuit=False,
        timeout_seconds=1.0,
    )


# ---------------------------------------------------------------------------
# 1. dev_short_circuit mode (default for tests + Phase 5 dev)
# ---------------------------------------------------------------------------


class TestDevShortCircuit:
    async def test_explicit_short_circuit_skips_upstream(self):
        client, transport = _build_client(
            lambda req: httpx.Response(500, json={})
        )
        verifier = _build_worker_verifier(client=client, dev_short_circuit=True)
        decision = await verifier.verify("any-token", remote_ip="1.2.3.4")
        await client.aclose()

        assert decision.verified is True
        assert decision.reason == "dev_short_circuit"
        assert decision.error_codes == ()
        assert transport.calls == []  # never hit upstream

    async def test_no_upstream_configured_short_circuits_automatically(self):
        # No worker_url + no cloudflare_secret + dev_short_circuit=False
        # → still short-circuits because there is nowhere to verify.
        verifier = TurnstileVerifier(dev_short_circuit=False)
        decision = await verifier.verify("token")
        assert decision.verified is True
        assert decision.reason == "dev_short_circuit"


# ---------------------------------------------------------------------------
# 2. Missing token (Mode 2 / Mode 3 with empty token)
# ---------------------------------------------------------------------------


class TestMissingToken:
    @pytest.mark.parametrize("token", [None, "", "   "])
    async def test_empty_token_short_circuits_to_missing(self, token):
        client, transport = _build_client(
            lambda req: httpx.Response(200, json={"success": True})
        )
        verifier = _build_worker_verifier(client=client)
        decision = await verifier.verify(token)
        await client.aclose()

        assert decision.verified is False
        assert decision.reason == "missing_token"
        # No upstream call when token is missing
        assert transport.calls == []


# ---------------------------------------------------------------------------
# 3. Worker verification — success path
# ---------------------------------------------------------------------------


class TestWorkerSuccess:
    async def test_worker_success_returns_verified(self):
        client, transport = _build_client(
            lambda req: httpx.Response(
                200, json={"success": True, "challenge_ts": "2026-06-13T00:00:00Z"}
            )
        )
        verifier = _build_worker_verifier(client=client)
        decision = await verifier.verify("good-token", remote_ip="1.2.3.4")
        await client.aclose()

        assert decision.verified is True
        assert decision.reason == "verified"
        assert decision.error_codes == ()

    async def test_worker_request_carries_token_and_remote_ip(self):
        captured: dict[str, Any] = {}

        def handler(req: httpx.Request) -> httpx.Response:
            captured["url"] = str(req.url)
            captured["body"] = req.content.decode()
            return httpx.Response(200, json={"success": True})

        client, _ = _build_client(handler)
        verifier = _build_worker_verifier(client=client)
        await verifier.verify("abc-token", remote_ip="9.9.9.9")
        await client.aclose()

        assert captured["url"] == "https://turnstile.test/verify"
        assert "abc-token" in captured["body"]
        assert "9.9.9.9" in captured["body"]


# ---------------------------------------------------------------------------
# 4. Worker rejection (Cloudflare says no)
# ---------------------------------------------------------------------------


class TestWorkerRejection:
    async def test_worker_failure_carries_error_codes(self):
        client, _ = _build_client(
            lambda req: httpx.Response(
                200,
                json={
                    "success": False,
                    "error_codes": ["invalid-input-response", "timeout-or-duplicate"],
                },
            )
        )
        verifier = _build_worker_verifier(client=client)
        decision = await verifier.verify("bad-token")
        await client.aclose()

        assert decision.verified is False
        assert decision.reason == "cloudflare_rejected"
        assert decision.error_codes == (
            "invalid-input-response",
            "timeout-or-duplicate",
        )

    async def test_worker_failure_with_single_string_error_code(self):
        # Some Cloudflare responses send a bare string; we normalise to a tuple.
        client, _ = _build_client(
            lambda req: httpx.Response(
                200, json={"success": False, "error_codes": "missing-input-response"}
            )
        )
        verifier = _build_worker_verifier(client=client)
        decision = await verifier.verify("bad")
        await client.aclose()

        assert decision.verified is False
        assert decision.error_codes == ("missing-input-response",)


# ---------------------------------------------------------------------------
# 5. Worker unavailable (fail-closed)
# ---------------------------------------------------------------------------


class TestWorkerUnavailable:
    async def test_500_response_fails_closed(self):
        client, _ = _build_client(
            lambda req: httpx.Response(500, json={"error": "internal"})
        )
        verifier = _build_worker_verifier(client=client)
        decision = await verifier.verify("token")
        await client.aclose()

        assert decision.verified is False
        assert decision.reason == "worker_unavailable"

    async def test_connect_error_fails_closed(self):
        def _raise(req: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("worker unreachable", request=req)

        client, _ = _build_client(_raise)
        verifier = _build_worker_verifier(client=client)
        decision = await verifier.verify("token")
        await client.aclose()

        assert decision.verified is False
        assert decision.reason == "worker_unavailable"

    async def test_malformed_json_fails_closed(self):
        client, _ = _build_client(
            lambda req: httpx.Response(
                200, content=b"not json", headers={"content-type": "text/plain"}
            )
        )
        verifier = _build_worker_verifier(client=client)
        decision = await verifier.verify("token")
        await client.aclose()

        assert decision.verified is False
        assert decision.reason == "worker_unavailable"


# ---------------------------------------------------------------------------
# 6. Direct siteverify path (no worker_url, cloudflare_secret only)
# ---------------------------------------------------------------------------


class TestDirectSiteverify:
    async def test_siteverify_url_and_form_body(self):
        captured: dict[str, Any] = {}

        def handler(req: httpx.Request) -> httpx.Response:
            captured["url"] = str(req.url)
            captured["body"] = req.content.decode()
            captured["content_type"] = req.headers.get("content-type", "")
            return httpx.Response(200, json={"success": True})

        client, _ = _build_client(handler)
        verifier = _build_siteverify_verifier(client=client)
        decision = await verifier.verify("user-token", remote_ip="1.1.1.1")
        await client.aclose()

        assert decision.verified is True
        assert decision.reason == "verified"
        assert captured["url"] == SITEVERIFY_URL
        # Form-encoded (not JSON) — siteverify expects x-www-form-urlencoded
        assert "application/x-www-form-urlencoded" in captured["content_type"]
        assert "secret=dev-secret" in captured["body"]
        assert "response=user-token" in captured["body"]
        assert "remoteip=1.1.1.1" in captured["body"]

    async def test_siteverify_handles_error_dash_codes(self):
        # Cloudflare siteverify uses `error-codes` (dash), worker uses
        # `error_codes` (underscore). Verifier must accept both.
        client, _ = _build_client(
            lambda req: httpx.Response(
                200,
                json={"success": False, "error-codes": ["invalid-input-secret"]},
            )
        )
        verifier = _build_siteverify_verifier(client=client)
        decision = await verifier.verify("any")
        await client.aclose()

        assert decision.verified is False
        assert decision.error_codes == ("invalid-input-secret",)


# ---------------------------------------------------------------------------
# 7. Lazy singleton + reset
# ---------------------------------------------------------------------------


class TestLazySingleton:
    def test_get_returns_same_instance_until_reset(self):
        reset_turnstile_verifier()
        first = get_turnstile_verifier()
        second = get_turnstile_verifier()
        assert first is second

        reset_turnstile_verifier()
        third = get_turnstile_verifier()
        assert third is not first

        reset_turnstile_verifier()  # leave state clean for other tests

    def test_default_dev_short_circuit_is_true(self):
        # No AGENTCOOK_TURNSTILE_DEV_SHORT_CIRCUIT in env → default True
        # so existing test/dev paths keep running without Cloudflare.
        assert DEFAULT_DEV_SHORT_CIRCUIT is True


# ---------------------------------------------------------------------------
# 8. chat.py endpoint integration — enforce mode rejects missing token
# ---------------------------------------------------------------------------


class TestChatEndpointEnforce:
    """End-to-end chat.py integration when AGENTCOOK_TURNSTILE_ENFORCE=true.

    Default off so all 22 existing chat_stream tests + 10 metadata tests
    keep PASS. These 3 tests cover the enforce branch by setting the env
    + injecting a verifier into the lazy singleton.
    """

    def _make_client(self, verifier: TurnstileVerifier, monkeypatch):
        from agentcook_app.main import create_app
        from agentcook_app.middleware import turnstile as turnstile_module
        from starlette.testclient import TestClient

        # Force the real (non-mock) path so the enforce branch fires
        monkeypatch.setenv("AGENTCOOK_LLM_PROVIDER", "qwen")
        monkeypatch.delenv("AGENTCOOK_CHAT_MOCK", raising=False)
        monkeypatch.setenv("AGENTCOOK_TURNSTILE_ENFORCE", "true")

        # Inject the test verifier — singleton would otherwise pick env-defaults
        turnstile_module._verifier_cache = verifier
        return TestClient(create_app())

    def test_enforce_rejects_missing_token(self, monkeypatch):
        verifier = TurnstileVerifier(
            cloudflare_secret="x", dev_short_circuit=False
        )
        client = self._make_client(verifier, monkeypatch)

        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-1", "message": "hi"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "TURNSTILE_REJECTED"
        assert body["detail"]["reason"] == "missing_token"

        reset_turnstile_verifier()

    def test_enforce_rejects_when_cloudflare_says_no(self, monkeypatch):
        client_http, _ = _build_client(
            lambda req: httpx.Response(
                200,
                json={"success": False, "error_codes": ["invalid-input-response"]},
            )
        )
        verifier = TurnstileVerifier(
            worker_url="https://turnstile.test/verify",
            http_client=client_http,
            dev_short_circuit=False,
        )
        client = self._make_client(verifier, monkeypatch)

        resp = client.post(
            "/api/v1/chat/stream",
            headers={"X-Turnstile-Token": "bad-token"},
            json={"session_id": "sess-1", "message": "hi"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "TURNSTILE_REJECTED"
        assert body["detail"]["reason"] == "cloudflare_rejected"
        assert body["detail"]["error_codes"] == ["invalid-input-response"]

        reset_turnstile_verifier()

    def test_mock_path_bypasses_enforce(self, monkeypatch):
        # Even with ENFORCE=true, mock path skips verification — this
        # protects contract tests + offline dev from suddenly needing
        # a Cloudflare account.
        from agentcook_app.main import create_app
        from agentcook_app.middleware import turnstile as turnstile_module
        from starlette.testclient import TestClient

        monkeypatch.setenv("AGENTCOOK_CHAT_MOCK", "true")
        monkeypatch.setenv("AGENTCOOK_TURNSTILE_ENFORCE", "true")
        # Even with a verifier that always rejects, mock path skips it
        turnstile_module._verifier_cache = TurnstileVerifier(
            cloudflare_secret="x", dev_short_circuit=False
        )

        client = TestClient(create_app())
        resp = client.post(
            "/api/v1/chat/stream",
            json={"session_id": "sess-1", "message": "hi"},
        )
        assert resp.status_code == 200  # mock path returned SSE
        assert "text/event-stream" in resp.headers["content-type"]

        reset_turnstile_verifier()
