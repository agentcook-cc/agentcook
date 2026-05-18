"""agentcook (FastAPI app shell) pytest harness smoke test."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_pytest_harness_in_app() -> None:
    assert 1 + 1 == 2
