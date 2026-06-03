#!/usr/bin/env bash
# Day 63 ESLint self-test: run eslint on the 5 fixtures and assert
# exit codes match expectations.
#
# Usage (from agentcook-app/ directory):
#   bash tests/eslint/run-check.sh
#
# Exit 0 if all 5 fixtures behave as expected; exit 1 on any deviation.

set -u

cd "$(dirname "$0")/../.." || exit 2

PASS=0
FAIL=0

check_fixture() {
  local fixture="$1"
  local expect="$2"  # "fail" or "pass"
  local label="$3"

  # Run eslint with --no-ignore so fixtures (otherwise excluded via
  # .eslintrc.cjs ignorePatterns to keep lint-staged green) are still
  # linted end-to-end here.
  if pnpm exec eslint --no-ignore "$fixture" >/dev/null 2>&1; then
    actual="pass"
  else
    actual="fail"
  fi

  if [ "$actual" = "$expect" ]; then
    echo "✅ [$label] $fixture → $actual (expected)"
    PASS=$((PASS + 1))
  else
    echo "❌ [$label] $fixture → $actual (expected $expect)"
    FAIL=$((FAIL + 1))
  fi
}

check_fixture tests/eslint/fixtures/trigger-literal.ts    fail "1/5 literal"
check_fixture tests/eslint/fixtures/trigger-template.ts   fail "2/5 template"
check_fixture tests/eslint/fixtures/trigger-identifier.ts fail "3/5 identifier"
check_fixture tests/eslint/fixtures/trigger-email.ts      fail "4/5 email"
check_fixture tests/eslint/fixtures/clean.ts              pass "5/5 clean"

echo "---"
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
