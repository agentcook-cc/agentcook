"""Consumer-side Pact: agentcook-admin → agentcook-java-crud.

Day 35-37 — CRUD operations for sessions and connectors that the admin
SPA exercises after Day 30's connector management feature ships.

Pairs with provider-side contract tests on the Java backend to ensure
the admin frontend's API calls match what the backend expects.

Four interactions cover session lifecycle and connector management:

    1. GET  /api/v1/sessions?userId=xxx   — list user's sessions
    2. POST /api/v1/sessions              — create new session
    3. GET  /api/v1/connectors?pluginId=xxx — list plugin's connectors
    4. DELETE /api/v1/connectors/{id}     — delete a connector

Field shapes mirror `docs/api/java-v1.yaml` (Java backend's
springdoc-generated spec, frozen Day 24 at v1.0).

NOTE — This file uses provider='agentcook-java-crud' instead of
'agentcook-java' because Pact v3 enforces one JSON file per
(consumer, provider) pair. The existing test_06 already claims
(agentcook-admin, agentcook-java), so we use a distinct provider
name to avoid collision while still targeting the same Java backend.
"""

from __future__ import annotations

import httpx
import pytest
from pact.v3 import Pact, match

CONSUMER = "agentcook-admin"
PROVIDER = "agentcook-java-crud"


@pytest.mark.contract
def test_admin_java_crud_contract(pacts_dir):
    """Session CRUD + connector management — the four calls admin makes post-Day 30."""
    pact = Pact(CONSUMER, PROVIDER).with_specification("V3")

    # --- Interaction 1: list sessions for a user ---------------------
    (
        pact.upon_receiving("list sessions for a specific user")
        .given("the user has at least one active session")
        .with_request(
            method="GET",
            path="/api/v1/sessions",
        )
        .with_query_parameter("userId", "00000000-0000-0000-0000-000000000001")
        .with_header("Authorization", "Bearer admin-access-token")
        .will_respond_with(200)
        .with_body(
            content_type="application/json",
            # SessionResponse record — id is UUID-shaped, userId references
            # the User entity, status reflects session state, createdAt is ISO-8601.
            body=match.each_like(
                {
                    "id": "00000000-0000-0000-0000-000000000002",
                    "userId": "00000000-0000-0000-0000-000000000001",
                    "title": "Debugging payment flow",
                    "status": "ACTIVE",
                    "createdAt": "2026-05-30T10:00:00Z",
                    "updatedAt": "2026-05-30T10:30:00Z",
                },
            ),
        )
    )

    # --- Interaction 2: create a new session -------------------------
    (
        pact.upon_receiving("create a new session for a user")
        .given("the target user exists")
        .with_request(
            method="POST",
            path="/api/v1/sessions",
        )
        .with_body(
            content_type="application/json",
            body={
                "userId": "00000000-0000-0000-0000-000000000001",
                "title": "New debugging session",
            },
        )
        .with_header("Authorization", "Bearer admin-access-token")
        .will_respond_with(201)
        .with_body(
            content_type="application/json",
            body={
                "id": "00000000-0000-0000-0000-000000000003",
                "userId": "00000000-0000-0000-0000-000000000001",
                "title": "New debugging session",
                "status": "ACTIVE",
                "createdAt": "2026-05-30T11:00:00Z",
                "updatedAt": "2026-05-30T11:00:00Z",
            },
        )
    )

    # --- Interaction 3: list connectors for a plugin -----------------
    (
        pact.upon_receiving("list connectors for a specific plugin")
        .given("the plugin has at least one connector configured")
        .with_request(
            method="GET",
            path="/api/v1/connectors",
        )
        .with_query_parameter("pluginId", "00000000-0000-0000-0000-000000000004")
        .with_header("Authorization", "Bearer admin-access-token")
        .will_respond_with(200)
        .with_body(
            content_type="application/json",
            # ConnectorResponse record — id is UUID-shaped, pluginId references
            # the Plugin entity, config holds connector-specific settings,
            # status indicates whether the connector is enabled.
            body=match.each_like(
                {
                    "id": "00000000-0000-0000-0000-000000000005",
                    "pluginId": "00000000-0000-0000-0000-000000000004",
                    "status": "CONNECTED",
                },
            ),
        )
    )

    # --- Interaction 4: delete a connector ---------------------------
    (
        pact.upon_receiving("delete an existing connector")
        .given("the connector exists and belongs to the requesting admin")
        .with_request(
            method="DELETE",
            path="/api/v1/connectors/00000000-0000-0000-0000-000000000005",
        )
        .with_header("Authorization", "Bearer admin-access-token")
        .will_respond_with(204)
    )

    with (
        pact.serve() as mock,
        httpx.Client(
            headers={"Authorization": "Bearer admin-access-token"}, trust_env=False
        ) as client,
    ):
        # Interaction 1 — list sessions
        r1 = client.get(
            f"{mock.url}/api/v1/sessions",
            params={"userId": "00000000-0000-0000-0000-000000000001"},
        )
        assert r1.status_code == 200
        sessions = r1.json()
        assert isinstance(sessions, list) and sessions
        assert sessions[0]["status"] == "ACTIVE"
        assert sessions[0]["userId"] == "00000000-0000-0000-0000-000000000001"

        # Interaction 2 — create session
        r2 = client.post(
            f"{mock.url}/api/v1/sessions",
            json={
                "userId": "00000000-0000-0000-0000-000000000001",
                "title": "New debugging session",
            },
        )
        assert r2.status_code == 201
        new_session = r2.json()
        assert new_session["title"] == "New debugging session"
        assert new_session["status"] == "ACTIVE"

        # Interaction 3 — list connectors
        r3 = client.get(
            f"{mock.url}/api/v1/connectors",
            params={"pluginId": "00000000-0000-0000-0000-000000000004"},
        )
        assert r3.status_code == 200
        connectors = r3.json()
        assert isinstance(connectors, list) and connectors
        assert connectors[0]["pluginId"] == "00000000-0000-0000-0000-000000000004"
        assert connectors[0]["status"] == "CONNECTED"

        # Interaction 4 — delete connector
        r4 = client.delete(
            f"{mock.url}/api/v1/connectors/00000000-0000-0000-0000-000000000005",
        )
        assert r4.status_code == 204

    pact.write_file(str(pacts_dir), overwrite=True)
