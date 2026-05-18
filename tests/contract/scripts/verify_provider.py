#!/usr/bin/env python
"""Run pact-verifier against a *running* HTTP provider.

Why a standalone script (in addition to `test_03_provider_verify_echo.py`):
    - CI / staging / prod can verify without booting pytest fixtures
    - Day 22 Agent A swaps `sample_provider` for the real `agentcook` shell —
      this script is the contract-verify entry point that doesn't change.
      A only changes which app is running on `--provider-base-url`.

Usage:
    # 1. boot whatever HTTP provider you want to verify
    uv run python -m uvicorn tests.contract.sample_provider.main:app \\
        --host 127.0.0.1 --port 8765 --log-level warning &

    # 2. run this script
    uv run python tests/contract/scripts/verify_provider.py \\
        --provider echo-api \\
        --provider-base-url http://127.0.0.1:8765 \\
        --provider-version 0.1.0-dev

    # All flags have sensible defaults — see --help.

Env vars (override defaults without touching the call site):
    PACT_BROKER_URL       default http://localhost:9292
    PACT_BROKER_USER      default pact
    PACT_BROKER_PASSWORD  default pact
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--provider",
        required=True,
        help='Provider name as registered on the broker (e.g. "echo-api", "agentcook").',
    )
    parser.add_argument(
        "--provider-base-url",
        required=True,
        help="HTTP base URL of the running provider (e.g. http://127.0.0.1:8765).",
    )
    parser.add_argument(
        "--provider-version",
        default=os.environ.get("PACT_PROVIDER_VERSION", "0.1.0-dev"),
        help="Provider application version (CI: pass git SHA).",
    )
    parser.add_argument(
        "--broker-url",
        default=os.environ.get("PACT_BROKER_URL", "http://localhost:9292"),
    )
    parser.add_argument(
        "--broker-username",
        default=os.environ.get("PACT_BROKER_USER", "pact"),
    )
    parser.add_argument(
        "--broker-password",
        default=os.environ.get("PACT_BROKER_PASSWORD", "pact"),
    )
    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="Skip --publish-verification-results (useful for ephemeral local checks).",
    )
    args = parser.parse_args()

    cmd = [
        "pact-verifier",
        f"--provider-base-url={args.provider_base_url}",
        f"--pact-broker-url={args.broker_url}",
        f"--pact-broker-username={args.broker_username}",
        f"--pact-broker-password={args.broker_password}",
        f"--provider={args.provider}",
        f"--provider-app-version={args.provider_version}",
    ]
    if not args.no_publish:
        cmd.append("--publish-verification-results")

    print(f"$ {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
