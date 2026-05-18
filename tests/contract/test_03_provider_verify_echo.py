"""Provider-side Pact verification: echo-api against the broker.

Runs the full e2e:
    1. boot the sample FastAPI provider on a random localhost port
    2. invoke `pact-verifier` (CLI shipped with pact-python) pointing at
       the running provider + the local broker
    3. pact-verifier pulls every contract for `provider="echo-api"`,
       replays each interaction's request, and asserts the response matches
    4. teardown — kill the FastAPI server

Day 22 Agent A swaps `sample_provider` for the real `agentcook` FastAPI
shell and the same verify pattern continues to work.
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


PROVIDER_NAME = "echo-api"
PROVIDER_VERSION = os.environ.get("PACT_PROVIDER_VERSION", "0.1.0-dev")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def provider_server() -> Iterator[str]:
    """Boot `sample_provider.main:app` on a random port; yield base URL."""
    port = _free_port()
    repo_root = Path(__file__).resolve().parents[2]
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tests.contract.sample_provider.main:app",
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
    deadline = time.time() + 15
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
            f"Provider failed to boot on {base_url}\n"
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
def test_provider_satisfies_broker_contracts(broker_url, broker_auth, provider_server):
    user, password = broker_auth

    cmd = [
        "pact-verifier",
        f"--provider-base-url={provider_server}",
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
