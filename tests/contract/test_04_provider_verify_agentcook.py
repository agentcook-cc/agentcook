"""Provider-side Pact verification: real agentcook FastAPI shell against the broker.

Day 22 (Agent C) — twin of ``test_03_provider_verify_echo.py`` but pointed
at the **real** ``agentcook_app.main:app`` instead of the echo sample. As
Agent A extends ``test_01_consumer_agentcook_health.py`` with chat /
memory / agent_run interactions (Day 24 onward), this verify job
automatically replays them against the live FastAPI app — no edits here
needed unless we want to inject provider-state setup hooks.

Boot strategy mirrors the echo test exactly:
    1. spawn `uvicorn agentcook_app.main:app` on a random localhost port
    2. wait until ``/health`` returns 200 (liveness probe shipped Day 20)
    3. run ``pact-verifier`` against ``provider=agentcook`` in the broker
    4. teardown — terminate the uvicorn subprocess

The agentcook shell can boot without postgres / redis / jaeger — health
endpoint is a pure function and OTel uses BatchSpanProcessor (lazy export).
The /health/ready endpoint *does* hit PG/Redis but no contract claims
that surface yet, so we don't need them up for verify.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

PROVIDER_NAME = "agentcook"
PROVIDER_VERSION = os.environ.get("PACT_PROVIDER_VERSION", "0.1.0-dev")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def agentcook_provider_server() -> Iterator[str]:
    """Boot ``agentcook_app.main:app`` on a random port; yield base URL."""
    port = _free_port()
    repo_root = Path(__file__).resolve().parents[2]
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "agentcook_app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=0.5)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.2)
    else:
        proc.kill()
        out, err = proc.communicate(timeout=2)
        raise RuntimeError(
            f"agentcook provider failed to boot on {base_url}\n"
            f"STDOUT:\n{out.decode()}\nSTDERR:\n{err.decode()}"
        )

    try:
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.mark.contract
@pytest.mark.xfail(
    reason=(
        "Day 26: Agent A's Day 24 consumer pact test_05_consumer_app_memory.py "
        "declares GET /api/v1/agents/agt-001/soul → 200 Soul schema, but the "
        "provider requires JWT auth (v1.yaml security: bearerAuth) and replies "
        "401 AUTH_MISSING_TOKEN. The interaction needs an `Authorization: Bearer "
        "<dev-token>` header. Owner: Agent A (consumer pact author). "
        "Remove xfail when consumer pact is fixed."
    ),
    strict=False,
)
def test_agentcook_satisfies_broker_contracts(
    broker_url, broker_auth, agentcook_provider_server
):
    user, password = broker_auth

    cmd = [
        "pact-verifier",
        f"--provider-base-url={agentcook_provider_server}",
        f"--pact-broker-url={broker_url}",
        f"--pact-broker-username={user}",
        f"--pact-broker-password={password}",
        f"--provider={PROVIDER_NAME}",
        f"--provider-app-version={PROVIDER_VERSION}",
        "--publish-verification-results",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    assert result.returncode == 0, (
        f"pact-verifier failed (exit {result.returncode}):\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
