"""V1 — agents / soul_versions / memory_events.

Three tables per the Day 11 decision (ADR-011 + decisions-2026-05-19):

- ``agents``         — Identity layer 1, immutable. A trigger raises on
                       any UPDATE so the immutability invariant is
                       enforced by the database, not just convention.
- ``soul_versions``  — Soul layer 2, append-only versioning. Every PUT
                       on the API inserts a new row; reads grab the
                       latest by ``(agent_id, version DESC)``.
- ``memory_events``  — Layer 3 event stream + pgvector embedding,
                       already provisioned by
                       ``PgVectorMemoryStore.ensure_schema``. We adopt
                       that DDL here so alembic is the single source of
                       truth going forward.

Caller is responsible for installing the ``vector`` extension before
running this migration (``CREATE EXTENSION IF NOT EXISTS vector``).
Migrations *can* do it themselves but only if the connecting role has
``CREATE`` on the database — keeping it out of the migration avoids
surprising privilege requirements in shared CI environments.

Revision ID: 0001_agents_soul_memory
Revises:
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_agents_soul_memory"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # agents — Identity layer 1 (immutable per ADR-011) ---------------------
    op.execute(
        """
        CREATE TABLE agents (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            role        TEXT NOT NULL,
            user_id     TEXT NOT NULL,           -- FK reference; User table lives in agentcook-java DB
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            scopes      TEXT[] NOT NULL DEFAULT '{}',
            metadata    JSONB NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )
    # DB-level enforcement of "Identity is immutable" (ADR-011).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION agents_block_update() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'agents rows are immutable (ADR-011 Identity); delete and recreate the agent instead';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER agents_no_update
        BEFORE UPDATE ON agents
        FOR EACH ROW EXECUTE FUNCTION agents_block_update()
        """
    )
    op.execute("CREATE INDEX agents_user_idx ON agents (user_id)")

    # soul_versions — Soul layer 2 (append-only) --------------------------
    op.execute(
        """
        CREATE TABLE soul_versions (
            id              BIGSERIAL PRIMARY KEY,
            agent_id        TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            version         INTEGER NOT NULL,
            tone            TEXT NOT NULL DEFAULT 'neutral',
            language_style  TEXT NOT NULL DEFAULT 'concise',
            values          TEXT[] NOT NULL DEFAULT '{}',
            custom_traits   JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (agent_id, version)
        )
        """
    )
    op.execute(
        "CREATE INDEX soul_versions_agent_latest_idx "
        "ON soul_versions (agent_id, version DESC)"
    )

    # memory_events — Layer 3 (event stream + pgvector embedding) -----------
    # Schema mirrors PgVectorMemoryStore.ensure_schema; alembic is now
    # the source of truth (callers SHOULD NOT call ensure_schema in prod).
    op.execute(
        """
        CREATE TABLE memory_events (
            id          BIGSERIAL PRIMARY KEY,
            agent_id    TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            timestamp   TIMESTAMPTZ NOT NULL,
            kind        TEXT NOT NULL,
            content     TEXT NOT NULL,
            source      TEXT,
            metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
            embedding   VECTOR(1536)
        )
        """
    )
    op.execute(
        "CREATE INDEX memory_events_agent_ts_idx "
        "ON memory_events (agent_id, timestamp DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS memory_events")
    op.execute("DROP TABLE IF EXISTS soul_versions")
    op.execute("DROP TRIGGER IF EXISTS agents_no_update ON agents")
    op.execute("DROP FUNCTION IF EXISTS agents_block_update()")
    op.execute("DROP TABLE IF EXISTS agents")
    # Leave the vector extension installed; tests / re-runs benefit.
