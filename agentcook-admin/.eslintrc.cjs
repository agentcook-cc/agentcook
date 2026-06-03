// Buffer Day 63 (Phase 5 backlog #10/15) — same rule set as
// agentcook-app/.eslintrc.cjs, replicated locally so each frontend
// sub-package owns its own ESLint resolution.
//
// Reason for duplication (vs. shared root config): both sub-packages
// already declare `eslint: ^8.57.0` in their own package.json and run
// their own `lint` script via Turborepo; a root config would require a
// monorepo-wide eslint install + plugin resolution rules. Keep them in
// sync with this comment as the contract; the two files MUST be edited
// together.

const CODENAME_PATTERN =
  '(?:HSF|Pandora|Diamond|Tair|EagleEye|RocketMQ|SchedulerX|Lindorm|TDDL|phoenix-[a-z][a-z0-9-]*)';

const PRIVATE_EMAIL_PATTERN =
  '@(?:accio|alibaba|taobao|aliyun-inc|ant-group)\\.(?:com|cn|net)';

const MESSAGE =
  '禁止内部代号 / 私有邮箱 — 使用对外化名替代。详 memory ' +
  '`desensitization-redlines.md` 化名映射表。';

// Phase 6 backlog #23 (Buffer Day 68 B) — `vue-eslint-parser` +
// `@typescript-eslint/parser` installed; src/ Vue SFCs + TS now parse
// cleanly. `plugin:vue/vue3-recommended` is intentionally NOT extended
// here — that's a separate Phase 6 backlog item; right now we only
// want the codename rules to apply with a parser that won't choke on
// Vue SFCs or TS keywords.
module.exports = {
  root: false,
  env: { browser: true, es2022: true, node: true },
  parser: 'vue-eslint-parser',
  parserOptions: {
    parser: '@typescript-eslint/parser',
    ecmaVersion: 2022,
    sourceType: 'module',
    extraFileExtensions: ['.vue'],
  },
  plugins: ['vue', '@typescript-eslint'],
  ignorePatterns: [
    'dist/**',
    'node_modules/**',
    'coverage/**',
    'playwright-report/**',
    'test-results/**',
    '.turbo/**',
    'tests/eslint/fixtures/**',
  ],
  rules: {
    'no-restricted-syntax': [
      'error',
      {
        selector: `Literal[value=/${CODENAME_PATTERN}/]`,
        message: MESSAGE,
      },
      {
        selector: `TemplateElement[value.raw=/${CODENAME_PATTERN}/]`,
        message: MESSAGE,
      },
      {
        selector: `Identifier[name=/^${CODENAME_PATTERN}$/]`,
        message: MESSAGE,
      },
      {
        selector: `Literal[value=/${PRIVATE_EMAIL_PATTERN}/]`,
        message: MESSAGE,
      },
    ],
  },
};
