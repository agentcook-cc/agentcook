"""agentcook-core pytest harness smoke test.

Intentionally does NOT import agentcook_core — that's the package author's
contract test (see test_protocols.py). This file only proves the pytest +
marker pipeline works inside this package's tests/ directory.
"""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_pytest_harness_in_core() -> None:
    assert 1 + 1 == 2
