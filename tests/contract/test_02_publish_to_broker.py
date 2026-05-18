"""Publish generated Pact contracts to the local self-hosted broker.

Why a test (rather than a separate script):
    Treating publish as a `pytest` step keeps it inside the dev loop:
        uv run pytest -m contract
    runs consumer → publish → verify in one go. CI can do the same.

Broker REST endpoint used:
    PUT /pacts/provider/{provider}/consumer/{consumer}/version/{version}

This test must run AFTER `test_consumer_echo.py` (alphabetical order
satisfies that). It's idempotent — re-publishing the same version
just overwrites; bumping `consumer_app_version` creates a new entry.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

# Stable consumer version for the dev loop. Real CI bumps to git SHA.
CONSUMER_APP_VERSION = os.environ.get("PACT_CONSUMER_VERSION", "0.1.0-dev")


@pytest.mark.contract
def test_publish_consumer_pacts(broker_url, broker_auth, pacts_dir):
    pact_files = sorted(pacts_dir.glob("*.json"))
    assert pact_files, f"No pacts in {pacts_dir} — did the consumer test run first?"

    for pact_file in pact_files:
        contract = json.loads(pact_file.read_text())
        consumer = contract["consumer"]["name"]
        provider = contract["provider"]["name"]

        url = (
            f"{broker_url}/pacts/provider/{provider}"
            f"/consumer/{consumer}/version/{CONSUMER_APP_VERSION}"
        )
        resp = httpx.put(
            url,
            content=pact_file.read_bytes(),
            headers={"Content-Type": "application/json"},
            auth=broker_auth,
            timeout=10.0,
        )
        # 200 = updated existing, 201 = created new — both fine
        assert resp.status_code in (200, 201), (
            f"Publish failed for {consumer}→{provider}: "
            f"{resp.status_code} {resp.text}"
        )
