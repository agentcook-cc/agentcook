"""Verify the live Python runtime against pacts published to the local broker."""

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
from pact.v3 import Verifier

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
def test_agentcook_satisfies_broker_contracts(broker_url, broker_auth, agentcook_provider_server):
    user, password = broker_auth

    (
        Verifier(PROVIDER_NAME, host="127.0.0.1")
        .add_transport(url=agentcook_provider_server)
        .broker_source(broker_url, username=user, password=password)
        .set_publish_options(PROVIDER_VERSION)
        .verify()
    )
