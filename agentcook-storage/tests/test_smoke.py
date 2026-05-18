"""agentcook-storage pytest harness smoke test."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_pytest_harness_in_storage() -> None:
    assert 1 + 1 == 2


@pytest.mark.integration
def test_storage_can_reach_pg(pg_url: str) -> None:
    """Sample integration test wiring storage into a real PostgreSQL container.

    Agent A: replace this with concrete PG-backed storage tests in Phase 1.
    """
    assert "postgresql" in pg_url
