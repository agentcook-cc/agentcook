// Fixture 1/5: string-literal codename. Expected to FAIL ESLint
// (no-restricted-syntax Literal selector). Run:
//   pnpm exec eslint tests/eslint/fixtures/trigger-literal.ts
// Expected: 1 error, exit code 1.

export const middlewareName = "HSF";
