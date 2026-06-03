// Buffer Day 63 (Phase 5 backlog #10/15): ESLint rules that block internal
// codename / private-email leakage at lint time. Hooks into the existing
// root lint-staged pipeline — no changes to package.json or pre-commit
// chain; simple-git-hooks already runs `npx lint-staged` which already
// runs `eslint --fix` on *.{ts,tsx,vue}.
//
// Rule families:
//   1. no-restricted-syntax with esquery selectors covering Literal,
//      TemplateElement, and Identifier nodes for codenames + internal
//      package patterns
//   2. Private-email literal block (substitution map per memory
//      `desensitization-redlines`)
//
// Note: ESLint does not analyse comments by default — this hook covers
// string literals / template literals / identifiers only. Comment-level
// cleanup is the coordinator's Day 63 morning task (grep + sed pass).
//
// To verify locally:
//   pnpm exec eslint tests/eslint/fixtures/with-trigger.ts   # exits 1
//   pnpm exec eslint tests/eslint/fixtures/clean.ts          # exits 0

const CODENAME_PATTERN =
  '(?:HSF|Pandora|Diamond|Tair|EagleEye|RocketMQ|SchedulerX|Lindorm|TDDL|phoenix-[a-z][a-z0-9-]*)';

const PRIVATE_EMAIL_PATTERN =
  '@(?:accio|alibaba|taobao|aliyun-inc|ant-group)\\.(?:com|cn|net)';

const MESSAGE =
  '禁止内部代号 / 私有邮箱 — 使用对外化名替代。详 memory ' +
  '`desensitization-redlines.md` 化名映射表。';

// Phase 6 backlog #23 (Buffer Day 68 B) — `@typescript-eslint/parser`
// installed; src/ TS + TSX now parses cleanly. The codename /
// private-email block runs across the whole source tree, not just
// fixtures and .cjs configs. Recommended rule sets
// (`plugin:@typescript-eslint/recommended`) are intentionally NOT
// extended yet — that's a separate Phase 6 backlog item; right now we
// only want the codename rules to apply with a parser that won't choke
// on `interface` / `type`.
module.exports = {
  root: false,
  env: { browser: true, es2022: true, node: true },
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
  },
  plugins: ['@typescript-eslint'],
  ignorePatterns: [
    'dist/**',
    'node_modules/**',
    'coverage/**',
    'playwright-report/**',
    'test-results/**',
    '.turbo/**',
    // Self-test fixtures contain trigger-word literals on purpose;
    // exclude from regular lint passes (lint-staged + Turborepo lint).
    // run-check.sh re-enables them via `eslint --no-ignore` so the
    // rules are still verified end-to-end on every release check.
    'tests/eslint/fixtures/**',
  ],
  rules: {
    'no-restricted-syntax': [
      'error',
      // String literals: const x = "HSF foo"
      {
        selector: `Literal[value=/${CODENAME_PATTERN}/]`,
        message: MESSAGE,
      },
      // Template literal chunks: `Pandora bar`
      {
        selector: `TemplateElement[value.raw=/${CODENAME_PATTERN}/]`,
        message: MESSAGE,
      },
      // Identifier names: const HSF = ...
      {
        selector: `Identifier[name=/^${CODENAME_PATTERN}$/]`,
        message: MESSAGE,
      },
      // Private email literals
      {
        selector: `Literal[value=/${PRIVATE_EMAIL_PATTERN}/]`,
        message: MESSAGE,
      },
    ],
  },
};
