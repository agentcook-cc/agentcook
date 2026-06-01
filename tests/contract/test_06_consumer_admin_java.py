"""Consumer-side Pact: agentcook-admin → agentcook-java.

Day 29 (Agent C) — first contract that crosses into the Java backend.
Pairs with `ContractScaffoldingTest.java` on the provider side, which
asserts the consumer/provider names line up with what we publish here:

    consumer = agentcook-admin
    provider = agentcook-java

Three interactions cover the auth + admin-management surfaces the admin
SPA exercises today. Each one mirrors a `javaClient.{get,post}` call
inside `agentcook-admin/src/`:

    1. POST /api/v1/auth/login         — admin login flow (LoginView.vue)
    2. GET  /api/v1/users              — UserListView.vue (mock today,
                                          will be the real path post-Day 30)
    3. POST /api/v1/plugins            — PluginCreateDialog.vue zip upload
                                          (multipart/form-data)

ConnectorController arrives Day 29 morning via D — once it ships, a
fourth interaction (`GET /api/v1/connectors`) lands in this same file
(don't add a fifth test/file — Pact v3 single-file-per-pair invariant,
see test_05's docstring).

Field shapes mirror `docs/api/java-v1.yaml` (Java backend's
springdoc-generated spec, frozen Day 24 at v1.0). Drift is caught by
the provider-side ContractScaffoldingTest + Day 29's CI integration.
"""

from __future__ import annotations

import httpx
import pytest
from pact.v3 import Pact

CONSUMER = "agentcook-admin"
PROVIDER = "agentcook-java"


@pytest.mark.contract
def test_admin_java_contract(pacts_dir):
    """Auth + user list + plugin upload — the three calls admin makes today."""
    pact = Pact(CONSUMER, PROVIDER).with_specification("V3")

    # --- Interaction 1: login ----------------------------------------
    # Java's AuthController dev profile returns a deterministic
    # `dev-token-{username}` for any non-empty creds, so we don't need
    # provider-state setup for this one.
    (
        pact.upon_receiving("login with valid credentials")
        .given("Java dev profile auth is enabled")
        .with_request(
            method="POST",
            path="/api/v1/auth/login",
        )
        .with_body(
            content_type="application/json",
            body={"username": "alice", "password": "dev-secret"},
        )
        .will_respond_with(200)
        .with_body(
            content_type="application/json",
            # AuthController returns a Java record serialised by Jackson —
            # camelCase by default. The auth store has a
            # snake_case/camelCase normaliser (Day 26 reverse fact-check),
            # but the wire shape we lock in here is what Jackson actually
            # emits.
            body={
                "accessToken": "dev-token-alice",
                "tokenType": "Bearer",
                "expiresIn": 3600,
            },
        )
    )

    # --- Interaction 2: list users -----------------------------------
    (
        pact.upon_receiving("list users for the admin user list view")
        .given("at least one user exists")
        .with_request(
            method="GET",
            path="/api/v1/users",
        )
        .will_respond_with(200)
        .with_body(
            content_type="application/json",
            # UserResponse record (Day 22-24 D) — id is a UUID-shaped string,
            # status is the UserStatus enum's name(). createdAt is ISO-8601.
            body=[
                {
                    "id": "01HXYZAB000000000000000001",
                    "email": "alice@example.com",
                    "displayName": "Alice",
                    "status": "ACTIVE",
                    "createdAt": "2026-05-30T08:00:00Z",
                },
            ],
        )
    )

    # --- Interaction 3: upload a plugin zip --------------------------
    # PluginController.upload accepts multipart/form-data. Pact v3
    # captures the Content-Type and request body shape; the actual
    # upload bytes are stubbed for the contract — provider verify
    # confirms the endpoint accepts the multipart shape and returns
    # the documented PluginResponse.
    # NOTE — pact-python v3 doesn't model multipart/form-data request
    # bodies cleanly: setting `with_body(content_type="multipart/...")`
    # collides with the v3 mock server's text/plain default and the
    # body matcher rejects the request. We lock the Content-Type-free
    # method+path here and let the Java-side IT
    # (`PluginControllerIntegrationTest`) cover the actual multipart
    # parsing. That split keeps the contract honest about what Pact
    # itself verifies vs. what provider tests verify.
    (
        pact.upon_receiving("upload a plugin (multipart body verified provider-side)")
        .given("the admin uploader has a valid plugin zip")
        .with_request(
            method="POST",
            path="/api/v1/plugins",
        )
        .will_respond_with(201)
        .with_body(
            content_type="application/json",
            body={
                "id": "01HXYZPL000000000000000001",
                "name": "demo-skill",
                "version": "0.1.0",
                "status": "DRAFT",
                "createdAt": "2026-06-05T09:00:00Z",
            },
        )
    )

    with pact.serve() as mock:
        # Interaction 1 — login
        r1 = httpx.post(
            f"{mock.url}/api/v1/auth/login",
            json={"username": "alice", "password": "dev-secret"},
        )
        assert r1.status_code == 200
        body1 = r1.json()
        assert body1["accessToken"].startswith("dev-token-")
        assert body1["tokenType"] == "Bearer"
        assert body1["expiresIn"] == 3600

        # Interaction 2 — list users
        r2 = httpx.get(f"{mock.url}/api/v1/users")
        assert r2.status_code == 200
        users = r2.json()
        assert isinstance(users, list) and users
        assert users[0]["status"] == "ACTIVE"

        # Interaction 3 — upload returns the documented PluginResponse.
        # We don't send a multipart body here (see NOTE above); the
        # Java provider IT covers the multipart parsing.
        r3 = httpx.post(f"{mock.url}/api/v1/plugins")
        assert r3.status_code == 201
        plugin = r3.json()
        assert plugin["status"] == "DRAFT"

    pact.write_file(str(pacts_dir), overwrite=True)
