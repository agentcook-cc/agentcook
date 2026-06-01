"""Publish generated Pact contracts to the local self-hosted broker.

Why a test (rather than a separate script):
    Treating publish as a `pytest` step keeps it inside the dev loop:
        uv run pytest -m contract
    runs consumer → publish → verify in one go. CI can do the same.

Broker REST endpoint used:
    PUT /pacts/provider/{provider}/consumer/{consumer}/version/{version}

This test must run AFTER `test_consumer_*.py` (alphabetical order
satisfies that).

Version strategy (Day 26 — Agent C fix for ci-local GAP #3):
    Broker rejects PUT with 409 when the same consumer version receives
    different pact content. Day 22-24 hardcoded "0.1.0-dev" worked while
    contracts were stable; as soon as Agent A added new interactions
    (Day 24 test_05) the existing 0.1.0-dev contract had different bytes
    and publish 409'd.

    Fix: derive the version from a SHA-256 of the pact file contents.
    Same bytes → same version (idempotent re-publish, broker 200).
    Different bytes → different version (broker 201 creates new entry).

    PACT_CONSUMER_VERSION env var still overrides for CI runs that want
    to pin to a git SHA. The default just stops local re-runs from 409'ing.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import httpx
import pytest


def _consumer_version_for(pact_file: Path) -> str:
    """Return a per-content version for this pact file.

    Override priority:
      1. ``PACT_CONSUMER_VERSION`` env var (CI typically sets git SHA)
      2. ``0.1.0-dev+<sha8>`` where sha is sha256(file_bytes)[:8]
    """
    if override := os.environ.get("PACT_CONSUMER_VERSION"):
        return override
    content_sha = hashlib.sha256(pact_file.read_bytes()).hexdigest()[:8]
    return f"0.1.0-dev+{content_sha}"


@pytest.mark.contract
def test_publish_consumer_pacts(broker_url, broker_auth, pacts_dir):
    pact_files = sorted(pacts_dir.glob("*.json"))
    assert pact_files, f"No pacts in {pacts_dir} — did the consumer test run first?"

    for pact_file in pact_files:
        contract = json.loads(pact_file.read_text())
        consumer = contract["consumer"]["name"]
        provider = contract["provider"]["name"]
        version = _consumer_version_for(pact_file)

        url = (
            f"{broker_url}/pacts/provider/{provider}"
            f"/consumer/{consumer}/version/{version}"
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
            f"Publish failed for {consumer}→{provider} v{version}: "
            f"{resp.status_code} {resp.text}"
        )
