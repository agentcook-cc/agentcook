"""Dump the agentcook FastAPI OpenAPI spec to ``docs/api/v1.yaml``.

Per Day 12 decision (decisions-2026-05-19 §A2):
- FastAPI's runtime ``/openapi.json`` stays as the live source of truth
  for orval consumers (B's frontend).
- This script materializes the spec to git so PRs surface API changes
  in diff review, and Day 13 wires a CI step to run ``schemathesis run``
  against the live app + ``schemathesis -v --base-url …`` for drift
  detection between the dumped file and the live endpoint.

Run: ``uv run python scripts/dump-openapi.py``
Output: ``docs/api/v1.yaml``
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from agentcook_app.main import create_app

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "docs" / "api" / "v1.yaml"


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    app = create_app()
    spec = app.openapi()
    # Stable, deterministic key ordering for clean git diffs.
    OUTPUT.write_text(
        yaml.safe_dump(spec, sort_keys=True, allow_unicode=True, width=120),
        encoding="utf-8",
    )
    paths_count = len(spec.get("paths", {}))
    schemas_count = len((spec.get("components") or {}).get("schemas") or {})
    print(
        f"Wrote {OUTPUT.relative_to(REPO_ROOT)}: "
        f"{paths_count} paths, {schemas_count} schemas"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
