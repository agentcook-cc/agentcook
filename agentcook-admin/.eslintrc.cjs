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

// Parser note: same rationale as agentcook-app/.eslintrc.cjs — leave
// default espree in place. Vue SFC source coverage needs
// `vue-eslint-parser` + `eslint-plugin-vue` (separate Buffer item,
// cross-cutting). The codename / email block layer here runs on every
// fixture and every plain `.cjs` / `.ts` / `.js` source file.
module.exports = {
  root: false,
  env: { browser: true, es2022: true, node: true },
  parserOptions: { ecmaVersion: 2022, sourceType: 'module' },
  ignorePatterns: [
    'dist/**',
    'node_modules/**',
    'coverage/**',
    '.turbo/**',
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
