"""Consumer Pact: agentcook-admin → agentcook (Python agent runtime).

What the Vue admin console calls on the runtime:

1. ``GET /health``                    — liveness on the dashboard
2. ``GET /api/v1/skills``             — SkillListView grid
3. ``GET /api/v1/skills/{id}``        — SkillDetailDrawer (adds the markdown body)

Shapes use type matchers (``like`` / ``each_like``): the contract pins the
fields and their types the admin reads, not the exact catalogue, so adding
a skill on the provider never breaks it. Verified without a broker by
``test_11_provider_verify_local.py`` against the live app.

pact-python v3 keys a pact file by ``(consumer, provider)`` and
``write_file`` replaces it wholesale, so every admin → agentcook
interaction lives in this one test.
"""

from __future__ import annotations

import httpx
import pytest
from pact.v3 import Pact, match

CONSUMER = "agentcook-admin"
PROVIDER = "agentcook"

SKILL = {
    "id": "summarize-conversation",
    "name": "Summarize Conversation",
    "description": "Condense a long chat into key bullet points.",
    "version": "1.0.0",
    "category": "memory",
    "updated_at": "2026-06-03T09:00:00+00:00",
}


@pytest.mark.contract
def test_admin_agentcook_contract(pacts_dir):
    pact = Pact(CONSUMER, PROVIDER).with_specification("V3")

    (
        pact.upon_receiving("a liveness probe")
        .with_request("GET", "/health")
        .will_respond_with(200)
        .with_body({"status": "ok"}, content_type="application/json")
    )
    (
        pact.upon_receiving("list skills for the SkillListView grid")
        .with_request("GET", "/api/v1/skills")
        .will_respond_with(200)
        .with_body(
            {"items": match.each_like(match.like(SKILL), min=1), "total": match.integer(7)},
            content_type="application/json",
        )
    )
    (
        pact.upon_receiving("fetch one skill with its body")
        .with_request("GET", "/api/v1/skills/summarize-conversation")
        .will_respond_with(200)
        .with_body(
            match.like({**SKILL, "body": "# Summarize a conversation\n..."}),
            content_type="application/json",
        )
    )

    with pact.serve() as mock:
        assert httpx.get(f"{mock.url}/health").json() == {"status": "ok"}
        skills = httpx.get(f"{mock.url}/api/v1/skills").json()
        assert skills["items"][0]["id"] == "summarize-conversation"
        detail = httpx.get(f"{mock.url}/api/v1/skills/summarize-conversation").json()
        assert detail["body"].startswith("# ")

    pact.write_file(str(pacts_dir), overwrite=True)
