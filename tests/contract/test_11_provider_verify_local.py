"""Provider verification for agentcook (the Python runtime) — no broker needed.

The consumer tests in this directory write their pacts to ``pacts/``. This
test boots the real app (offline mock model, in-memory storage, anonymous
access allowed) and replays every interaction whose provider is
``agentcook`` against it. It is the check that catches drift between what
the React app / Vue admin expect and what the runtime actually returns —
in every CI run, not only when a broker is around.

The broker-based flow (``test_02`` publish, ``test_04`` verify) still
exists for cross-repo, cross-version verification.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from pact.v3 import Verifier

PROVIDER = "agentcook"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def runtime_url() -> Iterator[str]:
    port = _free_port()
    env = {
        **os.environ,
        "AGENTCOOK_LLM_PROVIDER": "mock",
        "AGENTCOOK_STORAGE": "memory",
        "AGENTCOOK_AUTH_MODE": "optional",
        "AGENTCOOK_MOCK_DELAY_MS": "0",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "agentcook_app.main:app", "--port", str(port)],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            if httpx.get(f"{base}/health", timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    else:
        proc.kill()
        _, err = proc.communicate(timeout=5)
        raise RuntimeError(f"runtime did not start:\n{err.decode()}")
    try:
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _pacts_for(provider: str, pacts_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in pacts_dir.glob("*.json")
        if json.loads(p.read_text())["provider"]["name"] == provider
    )


@pytest.mark.contract
def test_runtime_satisfies_consumer_pacts(runtime_url, pacts_dir):
    pacts = _pacts_for(PROVIDER, Path(pacts_dir))
    consumers = {json.loads(p.read_text())["consumer"]["name"] for p in pacts}
    assert consumers >= {"agentcook-app", "agentcook-admin"}

    verifier = Verifier(PROVIDER, host="127.0.0.1").add_transport(url=runtime_url)
    for pact_file in pacts:
        verifier.add_source(pact_file)
    verifier.verify()
