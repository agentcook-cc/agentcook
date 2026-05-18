"""Consumer-side Pact test: agentcook-admin → echo-api.

4 interactions covering the canonical status-code shapes the real provider
will eventually serve too:

    GET /v1/echo?text=hello       → 200 EchoReply
    GET /v1/echo?text=             → 400 ErrorBody (empty text rejected)
    GET /v1/profiles/alice         → 200 Profile (happy path)
    GET /v1/profiles/ghost         → 404 ErrorBody (missing resource)

Uses pact-python v3 native API (Rust-backed). v2 Consumer/Provider classes
are deprecated — see pact-foundation/pact-python#396.

★ Why one test, four assertions
    pact-python v3 freezes provider-state edits once `pact.serve()` runs.
    Splitting into 4 tests with the same Pact handle hits
    `RuntimeError: The provider state could not be specified` on the 2nd
    test. So we register all 4 interactions, serve once, exercise each.
    A different consumer/provider pair → a separate test file.
"""

from __future__ import annotations

import httpx
import pytest
from pact.v3 import Pact

CONSUMER = "agentcook-admin"
PROVIDER = "echo-api"


@pytest.mark.contract
def test_admin_echo_api_contract(pacts_dir):
    pact = Pact(CONSUMER, PROVIDER).with_specification("V3")

    # 1. Happy echo
    (
        pact.upon_receiving("a request to echo the text 'hello'")
        .given("EchoProvider is configured with prefix=Echo")
        .with_request("GET", "/v1/echo")
        .with_query_parameter("text", "hello")
        .will_respond_with(200)
        .with_body(
            content_type="application/json",
            body={"reply": "[Echo] hello", "model": "echo-v0"},
        )
    )

    # 2. Empty text → 400 with structured ErrorBody
    (
        pact.upon_receiving("a request to echo an empty string")
        .given("EchoProvider rejects empty text")
        .with_request("GET", "/v1/echo")
        .with_query_parameter("text", "")
        .will_respond_with(400)
        .with_body(
            content_type="application/json",
            body={"error": "text must not be empty", "code": "empty_text"},
        )
    )

    # 3. Existing profile → 200
    (
        pact.upon_receiving("a request for an existing profile")
        .given("a profile exists with id 'alice'")
        .with_request("GET", "/v1/profiles/alice")
        .will_respond_with(200)
        .with_body(
            content_type="application/json",
            body={"id": "alice", "display_name": "Alice"},
        )
    )

    # 4. Missing profile → 404 with structured ErrorBody
    (
        pact.upon_receiving("a request for a non-existent profile")
        .given("no profile exists with id 'ghost'")
        .with_request("GET", "/v1/profiles/ghost")
        .will_respond_with(404)
        .with_body(
            content_type="application/json",
            body={
                "error": "profile 'ghost' not found",
                "code": "profile_missing",
            },
        )
    )

    with pact.serve() as mock:
        # 1. happy
        r = httpx.get(f"{mock.url}/v1/echo", params={"text": "hello"})
        assert r.status_code == 200
        assert r.json() == {"reply": "[Echo] hello", "model": "echo-v0"}

        # 2. 400
        r = httpx.get(f"{mock.url}/v1/echo", params={"text": ""})
        assert r.status_code == 400
        assert r.json() == {"error": "text must not be empty", "code": "empty_text"}

        # 3. profile 200
        r = httpx.get(f"{mock.url}/v1/profiles/alice")
        assert r.status_code == 200
        assert r.json() == {"id": "alice", "display_name": "Alice"}

        # 4. profile 404
        r = httpx.get(f"{mock.url}/v1/profiles/ghost")
        assert r.status_code == 404
        assert r.json() == {
            "error": "profile 'ghost' not found",
            "code": "profile_missing",
        }

    pact.write_file(str(pacts_dir), overwrite=True)
