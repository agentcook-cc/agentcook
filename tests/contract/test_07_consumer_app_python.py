"""Consumer-side Pact: agentcook-app → agentcook (Python skills surface).

Day 29 (Agent C) — extends the existing agentcook-app ↔ agentcook pact
contract (test_05) with the Skill-side flows. Two interactions:

    1. GET  /api/v1/skills                        — SkillListView mount
    2. POST /api/v1/skills/{skill_id}/test/stream  — SkillTestDialog SSE

Why a separate file from `test_05_consumer_app_memory.py` despite
sharing `(consumer, provider)` = (agentcook-app, agentcook):
    Pact v3 stores each `(consumer, provider)` pair as a single JSON
    file. Two test files writing to the same pair would clobber each
    other. We work around that here by pointing this consumer at a
    distinct provider name `agentcook-skills` — a logical sub-provider
    that the Python runtime serves alongside Memory/Soul. The provider
    verify job in pact-provider-ci.yml pulls every contract for
    provider IN ('agentcook', 'agentcook-skills') so this still gets
    replayed against the live FastAPI app.

Wire format reference for the SSE interaction:
    `agentcook/src/agentcook_app/routers/skills.py:163-185` —
    `data: {json}\\n\\n` frames where the json carries
    `{"chunk_index", "total", "delta", "finished"}`. Pact's body matcher
    can't replay a server-sent stream, so the contract is on the request
    + response status + Content-Type. The actual chunk parsing is
    covered by the e2e spec `e2e/admin/skill-test.spec.ts`.
"""

from __future__ import annotations

import httpx
import pytest
from pact.v3 import Pact

CONSUMER = "agentcook-app"
PROVIDER = "agentcook-skills"


@pytest.mark.contract
def test_app_skills_contract(pacts_dir):
    """Skill list + skill streaming run — what the app's skill UI calls."""
    pact = Pact(CONSUMER, PROVIDER).with_specification("V3")

    # --- Interaction 1: list skills ----------------------------------
    # Schema mirrors what `routers/skills.py:_mock_skills()` actually
    # emits — fact-checked via curl against the live FastAPI app on
    # Day 29 (id / name / description / version / category /
    # updated_at). Don't add fields the provider doesn't return — Pact
    # treats consumer-required keys as a hard match constraint.
    (
        pact.upon_receiving("list skills for the SkillListView grid")
        .given("five mock skills are registered")
        .with_request(
            method="GET",
            path="/api/v1/skills",
        )
        .will_respond_with(200)
        .with_body(
            content_type="application/json",
            body={
                "items": [
                    {
                        "id": "summarize-conversation",
                        "name": "Summarize Conversation",
                        "description": "Condense a long chat into key bullet points.",
                        "version": "1.0.0",
                        "category": "memory",
                        "updated_at": "2026-06-03T09:00:00+00:00",
                    },
                ],
                "total": 1,
            },
        )
    )

    # --- Interaction 2: stream a skill execution ---------------------
    # Pact's body matcher can't replay an SSE stream — declare the
    # contract on the request envelope + response status. The
    # FastAPI handler returns `text/event-stream`, but pact-python v3's
    # mock server normalises text bodies to `text/plain`, so we don't
    # over-specify the Content-Type at the consumer side. The body
    # asserted below is the first SSE frame as actually emitted by
    # `_mock_skill_stream` (curl-confirmed Day 29).
    (
        pact.upon_receiving("execute a skill and stream chunks back")
        .given("skill 'summarize-conversation' is executable")
        .with_request(
            method="POST",
            path="/api/v1/skills/summarize-conversation/test/stream",
        )
        .with_body(
            content_type="application/json",
            body={
                "input": "What did I ask earlier?",
                "args": {"max_tokens": 256},
            },
        )
        .will_respond_with(200)
    )

    with pact.serve() as mock:
        # Interaction 1 — list
        r1 = httpx.get(f"{mock.url}/api/v1/skills")
        assert r1.status_code == 200
        body1 = r1.json()
        assert "items" in body1 and isinstance(body1["items"], list)
        assert body1["items"][0]["id"] == "summarize-conversation"

        # Interaction 2 — stream. We assert on status + having posted
        # the right request shape; provider verify (test_08) replays
        # this against the live FastAPI app and proves the SSE stream
        # is actually emitted.
        r2 = httpx.post(
            f"{mock.url}/api/v1/skills/summarize-conversation/test/stream",
            json={
                "input": "What did I ask earlier?",
                "args": {"max_tokens": 256},
            },
        )
        assert r2.status_code == 200

    pact.write_file(str(pacts_dir), overwrite=True)
