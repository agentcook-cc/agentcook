"""V2 — conversations / conversation_messages.

Multi-turn chat transcripts for the agent loop (ADR-020). Kept separate
from ``memory_events`` (ADR-011 layer 3): transcripts are per-session,
append-only, replayed verbatim (including tool calls / tool results) and
owned by exactly one user; memory events are per-agent, summarized and
retrieved semantically.

``conversations.user_id`` is the JWT ``sub`` (the User aggregate lives in
agentcook-java's database, so this is a reference, not a foreign key).

Revision ID: 0002_conversations
Revises: 0001_agents_soul_memory
Create Date: 2026-10-14
"""

from __future__ import annotations

from alembic import op

revision = "0002_conversations"
down_revision = "0001_agents_soul_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE conversations (
            id            TEXT PRIMARY KEY,
            user_id       TEXT NOT NULL,
            agent         TEXT NOT NULL,
            title         TEXT NOT NULL,
            metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
            message_count INTEGER NOT NULL DEFAULT 0,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX conversations_user_updated_idx ON conversations (user_id, updated_at DESC)"
    )
    op.execute(
        """
        CREATE TABLE conversation_messages (
            id              BIGSERIAL PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            seq             INTEGER NOT NULL,
            role            TEXT NOT NULL,
            content         TEXT NOT NULL,
            name            TEXT,
            tool_call_id    TEXT,
            tool_calls      JSONB,
            metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (conversation_id, seq)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS conversation_messages")
    op.execute("DROP TABLE IF EXISTS conversations")
