"""Verify the real Java provider without a broker.

Set AGENTCOOK_JAVA_PROVIDER_URL to an isolated development instance. The test
registers/logs in its dedicated fixture account and substitutes fresh tokens
in the consumer pact; no auth bypass or production provider-state endpoint.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import httpx
import pytest
from pact.v3 import Verifier


@pytest.mark.contract
def test_java_satisfies_app_pact(tmp_path):
    base = os.environ.get("AGENTCOOK_JAVA_PROVIDER_URL")
    if not base:
        pytest.skip("Set AGENTCOOK_JAVA_PROVIDER_URL to verify against a running Java backend")
    spec = importlib.util.spec_from_file_location(
        "app_java_contract", Path(__file__).with_name("test_10_consumer_app_chat_sessions.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.build_pact().write_file(str(tmp_path), overwrite=True)
    with httpx.Client(base_url=base, trust_env=False) as client:
        credentials = {"username": module.USERNAME, "password": module.PASSWORD}
        registered = client.post("/api/v1/auth/register", json=credentials)
        assert registered.status_code in (201, 409), registered.text
        login = client.post("/api/v1/auth/login", json=credentials)
        assert login.status_code == 200, login.text
        tokens = login.json()
    pact_file = next(tmp_path.glob("*.json"))
    pact = json.loads(pact_file.read_text())
    for interaction in pact["interactions"]:
        request = interaction["request"]
        if request["path"] == "/api/v1/auth/refresh":
            request["body"]["refreshToken"] = tokens["refreshToken"]
        if "Authorization" in request.get("headers", {}):
            request["headers"]["Authorization"] = f"Bearer {tokens['accessToken']}"
    pact_file.write_text(json.dumps(pact))
    Verifier(module.JAVA_PROVIDER, host="127.0.0.1").add_transport(url=base).add_source(
        pact_file
    ).verify()
