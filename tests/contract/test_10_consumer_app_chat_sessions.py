"""React app → Java: password login, refresh, quota and current profile.

Conversations and tools belong to the runtime (test_05). These are the
Java calls actually emitted by stores/auth.ts and hooks/useQuota.ts.
"""

from __future__ import annotations

import httpx
import pytest
from pact.v3 import Pact, match

JAVA_CONSUMER = "agentcook-app"
JAVA_PROVIDER = "agentcook-java-app"
USERNAME = "contract-reader"
PASSWORD = "contract-password-123"
ACCESS = "contract-access"
REFRESH = "contract-refresh"


def token_body():
    return {
        "accessToken": match.string("signed.access.token"),
        "tokenType": "Bearer",
        "expiresIn": match.integer(3600),
        "refreshToken": match.string("signed.refresh.token"),
        "refreshExpiresIn": match.integer(2592000),
    }


def build_pact():
    pact = Pact(JAVA_CONSUMER, JAVA_PROVIDER).with_specification("V3")
    for path, body in [
        ("login", {"username": USERNAME, "password": PASSWORD}),
        ("refresh", {"refreshToken": REFRESH}),
    ]:
        (
            pact.upon_receiving(f"app {path}")
            .with_request("POST", f"/api/v1/auth/{path}")
            .with_body(body, content_type="application/json")
            .will_respond_with(200)
            .with_body(token_body(), content_type="application/json")
        )
    (
        pact.upon_receiving("app current quota")
        .with_request("GET", "/api/v1/quota")
        .with_header("Authorization", f"Bearer {ACCESS}")
        .will_respond_with(200)
        .with_body(
            {
                "free_questions_used": match.integer(0),
                "free_questions_quota": match.integer(2),
                "used": match.integer(0),
                "quota": match.integer(2),
                "remaining": match.integer(2),
            },
            content_type="application/json",
        )
    )
    (
        pact.upon_receiving("app current user")
        .with_request("GET", "/api/v1/users/me")
        .with_header("Authorization", f"Bearer {ACCESS}")
        .will_respond_with(200)
        .with_body(
            match.like(
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "email": f"{USERNAME}@dev.local",
                    "nickname": USERNAME,
                    "status": "ACTIVE",
                    "createdAt": "2026-01-01T00:00:00Z",
                    "updatedAt": "2026-01-01T00:00:00Z",
                }
            ),
            content_type="application/json",
        )
    )
    return pact


@pytest.mark.contract
def test_app_java_auth_and_quota_contract(pacts_dir):
    pact = build_pact()
    with pact.serve() as mock, httpx.Client(base_url=str(mock.url), trust_env=False) as client:
        login = client.post("/api/v1/auth/login", json={"username": USERNAME, "password": PASSWORD})
        assert login.status_code == 200
        assert login.json()["refreshToken"]
        refreshed = client.post("/api/v1/auth/refresh", json={"refreshToken": REFRESH})
        assert refreshed.status_code == 200
        assert refreshed.json()["tokenType"] == "Bearer"
        quota = client.get("/api/v1/quota", headers={"Authorization": f"Bearer {ACCESS}"})
        assert quota.status_code == 200
        assert quota.json()["free_questions_used"] == quota.json()["used"]
        profile = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {ACCESS}"})
        assert profile.status_code == 200
        assert profile.json()["nickname"] == USERNAME
    pact.write_file(str(pacts_dir), overwrite=True)
