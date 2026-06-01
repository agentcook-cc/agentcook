"""Consumer-side Pact test: agentcook-admin → agentcook (real FastAPI shell).

Day 22 (Agent C) — scaffold for the **real** agentcook provider, separate
from the echo-api sample. Day 24 Agent A freezes the OpenAPI; this file
gets extended with chat / memory / agent_run interactions then.

Today's single interaction targets the liveness probe Agent C shipped on
Day 20: ``GET /health → 200 {"status": "ok"}`` — a stable contract that
exists in code today, so the full link (consumer → publish → provider
verify) actually runs end-to-end and proves the scaffolding works before
the API surface is frozen.

Why a separate file from ``test_01_consumer_echo.py``: pact-python v3
keys interactions by ``(consumer, provider)``. ``echo-api`` and
``agentcook`` are different providers, so they need separate Pact handles
— see the docstring in ``test_01_consumer_echo.py`` for the v3
provider-state freezing constraint that forces this.
"""

from __future__ import annotations

import httpx
import pytest
from pact.v3 import Pact

CONSUMER = "agentcook-admin"
PROVIDER = "agentcook"


@pytest.mark.contract
def test_admin_agentcook_contract(pacts_dir):
    pact = Pact(CONSUMER, PROVIDER).with_specification("V3")

    (
        pact.upon_receiving("a liveness probe")
        .given("agentcook FastAPI runtime is alive")
        .with_request("GET", "/health")
        .will_respond_with(200)
        .with_body(
            content_type="application/json",
            body={"status": "ok"},
        )
    )

    with pact.serve() as mock:
        r = httpx.get(f"{mock.url}/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    pact.write_file(str(pacts_dir), overwrite=True)
