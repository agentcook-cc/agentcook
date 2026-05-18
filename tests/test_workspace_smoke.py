"""Monorepo-level smoke tests — verify pytest collection and shared fixtures."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_monorepo_pytest_collects() -> None:
    """Pytest can collect a unit test from the workspace root."""
    assert True


@pytest.mark.integration
def test_pg_container_boots(pg_url: str) -> None:
    """Session-scoped PostgreSQL fixture yields a usable connection URL."""
    assert pg_url.startswith("postgresql")


@pytest.mark.integration
def test_redis_client_pings(redis_client) -> None:
    """Session-scoped Redis fixture yields a client that responds to PING."""
    assert redis_client.ping() is True
