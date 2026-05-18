"""Shared fixtures for Pact contract tests.

Convention:
    - `consumer_name` / `provider_name` are stable IDs the broker uses to
      group contracts. Don't rename without coordinating with the broker
      owner (Agent C).
    - `pacts_dir` is where pact-python writes generated JSON contracts
      before they're published to the broker.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest

PACT_BROKER_URL = os.environ.get("PACT_BROKER_URL", "http://localhost:9292")
PACT_BROKER_USER = os.environ.get("PACT_BROKER_USER", "pact")
PACT_BROKER_PASSWORD = os.environ.get("PACT_BROKER_PASSWORD", "pact")


def _broker_reachable() -> bool:
    try:
        r = httpx.get(
            f"{PACT_BROKER_URL}/diagnostic/status/heartbeat",
            timeout=2.0,
        )
        return r.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def broker_url() -> str:
    if not _broker_reachable():
        pytest.skip(f"Pact broker not reachable at {PACT_BROKER_URL}")
    return PACT_BROKER_URL


@pytest.fixture(scope="session")
def broker_auth() -> tuple[str, str]:
    return PACT_BROKER_USER, PACT_BROKER_PASSWORD


@pytest.fixture(scope="session")
def pacts_dir() -> Path:
    d = Path(__file__).parent / "pacts"
    d.mkdir(exist_ok=True)
    return d
