"""Admin password login, authenticated user list and real multipart plugin upload."""

from __future__ import annotations

import json
import zipfile

import httpx
import pytest
from pact.v3 import Pact, match

CONSUMER = "agentcook-admin"
PROVIDER = "agentcook-java"


@pytest.mark.contract
def test_admin_java_contract(pacts_dir, tmp_path):
    pact = Pact(CONSUMER, PROVIDER).with_specification("V3")
    headers = {"Authorization": "Bearer admin-access-token"}
    (
        pact.upon_receiving("admin password login")
        .given("admin account with a password exists")
        .with_request("POST", "/api/v1/auth/login")
        .with_body(
            {"username": "admin", "password": "admin-password-123"}, content_type="application/json"
        )
        .will_respond_with(200)
        .with_body(
            {
                "accessToken": match.string("signed.access.token"),
                "tokenType": "Bearer",
                "expiresIn": match.integer(3600),
                "refreshToken": match.string("signed.refresh.token"),
                "refreshExpiresIn": match.integer(2592000),
            },
            content_type="application/json",
        )
    )
    (
        pact.upon_receiving("admin lists users")
        .given("an administrator and at least one user exist")
        .with_request("GET", "/api/v1/users")
        .with_header("Authorization", headers["Authorization"])
        .will_respond_with(200)
        .with_body(
            match.each_like(
                {
                    "id": match.uuid("00000000-0000-0000-0000-000000000001"),
                    "email": "alice@example.com",
                    "nickname": "Alice",
                    "status": "ACTIVE",
                    "createdAt": "2026-01-01T00:00:00Z",
                    "updatedAt": "2026-01-01T00:00:00Z",
                }
            ),
            content_type="application/json",
        )
    )
    package = tmp_path / "contract-plugin.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(
            "plugin.json",
            json.dumps(
                {
                    "name": "contract-plugin",
                    "version": "1.0.0",
                    "kind": "WEBHOOK",
                    "description": "Contract fixture",
                }
            ),
        )
    (
        pact.upon_receiving("admin uploads a plugin zip")
        .given("the plugin version has not been registered")
        .with_request("POST", "/api/v1/plugins")
        .with_header("Authorization", headers["Authorization"])
        .with_multipart_file(
            "file", package, content_type="application/zip", boundary="contract-boundary"
        )
        .will_respond_with(201)
        .with_body(
            match.like(
                {
                    "id": "00000000-0000-0000-0000-000000000002",
                    "name": "contract-plugin",
                    "version": "1.0.0",
                    "kind": "WEBHOOK",
                    "status": "DRAFT",
                }
            ),
            content_type="application/json",
        )
    )
    with pact.serve() as mock, httpx.Client(base_url=str(mock.url), trust_env=False) as client:
        response = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "admin-password-123"}
        )
        assert response.status_code == 200
        assert response.json()["refreshToken"]
        users = client.get("/api/v1/users", headers=headers)
        assert users.status_code == 200
        assert users.json()[0]["nickname"] == "Alice"
        uploaded = client.post(
            "/api/v1/plugins",
            headers=headers,
            files={"file": (package.name, package.read_bytes(), "application/zip")},
        )
        assert uploaded.status_code == 201
        assert uploaded.json()["status"] == "DRAFT"
    pact.write_file(str(pacts_dir), overwrite=True)
