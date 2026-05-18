"""Format-only lint for ``docs/api/v1.yaml``.

Author decision §A2 (Day 12): the dumped OpenAPI lives in git so PRs
show API diffs. To keep that diff signal high, we lint **format only**
— we deliberately do NOT enforce freshness here (that's a CI-time
check, per author §A1).

Checks:
1. File parses as YAML.
2. Top-level keys are sorted (matches ``dump-openapi.py``'s
   ``sort_keys=True`` output).
3. No tab indentation (yaml.safe_dump uses spaces only).

Exits 0 on pass, 1 on lint failure. Hook this from
``.pre-commit-config.yaml`` if you want it to run locally.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "docs" / "api" / "v1.yaml"


def main() -> int:
    if not TARGET.exists():
        print(f"ERROR: {TARGET.relative_to(REPO_ROOT)} not found", file=sys.stderr)
        return 1

    raw = TARGET.read_text(encoding="utf-8")

    try:
        spec = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        print(f"ERROR: invalid YAML: {exc}", file=sys.stderr)
        return 1

    if not isinstance(spec, dict):
        print("ERROR: top-level OpenAPI document must be a mapping", file=sys.stderr)
        return 1

    top_keys = list(spec.keys())
    if top_keys != sorted(top_keys):
        print(
            "ERROR: top-level keys are not sorted. "
            "Re-run `uv run python scripts/dump-openapi.py` and re-commit.",
            file=sys.stderr,
        )
        return 1

    if "\t" in raw:
        print("ERROR: tab indentation detected — use spaces.", file=sys.stderr)
        return 1

    paths_count = len(spec.get("paths", {}))
    schemas_count = len((spec.get("components") or {}).get("schemas") or {})
    print(f"OK: {paths_count} paths, {schemas_count} schemas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
