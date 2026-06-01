"""Consumer-side Pact templates: agentcook-app → agentcook (Memory + Soul).

Day 24 (Agent A) — interaction templates landed alongside the v1.0 spec
freeze. Two consumer flows that the React app drives end-to-end:

1. **Diary append** — POST a memory event from the chat UI when the user
   completes a turn. Exercised by ``MessageBubble`` after every reply.
2. **Soul fetch** — GET the agent's stable personality config when the
   chat session opens. Exercised by ``ChatPage`` mount.

Both target frozen v1.0 paths; the field shapes here mirror the
``MemoryEventCreate`` / ``MemoryEventResponse`` / ``SoulResponse``
schemas in ``docs/api/v1.yaml``. Any drift between this file and
``v1.yaml`` is a freeze violation — the provider verify run will catch
it (Agent C's Day 24 CI wires that up).

Why a separate consumer name from ``test_01_consumer_agentcook_health``:
``agentcook-admin`` covers admin/ops contracts; ``agentcook-app``
covers end-user chat flows. Pact v3 keys interactions by
``(consumer, provider)`` — keeping them split avoids the two
``.write_file()`` calls fighting over the same JSON.

Why a single test with two interactions (not two tests):
``Pact.write_file`` overwrites the JSON wholesale, so multiple tests
each calling ``write_file`` race over the same path and only the last
winner survives. Stack both interactions on the same ``Pact`` builder
and write once — that's the v3 idiom.

Provider state setup note (for Agent C's Day 24 CI):
the ``given(...)`` clauses below — ``agent agt-001 has a soul
configured`` and ``agent agt-001 exists with a fresh diary`` — require
provider-side state hooks before ``pact-verifier`` will satisfy them.
The hooks are C's territory (provider verify CI). Until they land,
running ``test_04_provider_verify_agentcook`` against this app pact
will fail at the Soul GET / Diary POST steps — that's expected, not a
contract drift. The pact JSON itself is authoritative for B's codegen.
"""

from __future__ import annotations

import httpx
import pytest
from pact.v3 import Pact

CONSUMER = "agentcook-app"
PROVIDER = "agentcook"


@pytest.mark.contract
def test_app_memory_and_soul_contract(pacts_dir):
    """Memory append + Soul fetch — the two end-user flows the chat UI drives."""
    pact = Pact(CONSUMER, PROVIDER).with_specification("V3")

    # --- Interaction 1: append a diary entry --------------------------
    (
        pact.upon_receiving("append a memory event")
        .given("agent agt-001 exists with a fresh diary")
        .with_request(
            method="POST",
            path="/api/v1/agents/agt-001/memory/events",
        )
        .with_body(
            content_type="application/json",
            body={
                "kind": "observation",
                "content": "user asked about pricing tiers",
                "source": "chat-ui",
            },
        )
        .will_respond_with(201)
        .with_body(
            content_type="application/json",
            body={
                "event_id": "evt-12345",
                "timestamp": "2026-05-31T12:00:00Z",
                "kind": "observation",
                "content": "user asked about pricing tiers",
                "source": "chat-ui",
            },
        )
    )

    # --- Interaction 2: fetch current soul config ---------------------
    (
        pact.upon_receiving("fetch current soul config")
        .given("agent agt-001 has a soul configured")
        .with_request(
            method="GET",
            path="/api/v1/agents/agt-001/soul",
        )
        .will_respond_with(200)
        .with_body(
            content_type="application/json",
            body={
                "tone": "warm",
                "language_style": "concise",
                "values": ["honesty", "clarity"],
                "custom_traits": {},
            },
        )
    )

    with pact.serve() as mock:
        # Exercise interaction 1
        r1 = httpx.post(
            f"{mock.url}/api/v1/agents/agt-001/memory/events",
            json={
                "kind": "observation",
                "content": "user asked about pricing tiers",
                "source": "chat-ui",
            },
        )
        assert r1.status_code == 201
        assert r1.json()["kind"] == "observation"
        assert r1.json()["event_id"]

        # Exercise interaction 2
        r2 = httpx.get(f"{mock.url}/api/v1/agents/agt-001/soul")
        assert r2.status_code == 200
        assert r2.json()["tone"] == "warm"
        assert "values" in r2.json()

    pact.write_file(str(pacts_dir), overwrite=True)
