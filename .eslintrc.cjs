// Root ESLint config. lint-staged runs `eslint --fix` from the repo root,
// so every staged TS/Vue file needs a config to resolve to — including
// e2e/ specs and root tool configs that live outside a package.
//
// Package configs (agentcook-app/.eslintrc.cjs, agentcook-admin/.eslintrc.cjs)
// set `root: false` and cascade on top of this one: they keep their own
// parser setup and the codename / private-email rules.
module.exports = {
  root: true,
  env: { browser: true, es2022: true, node: true },
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: 2022, sourceType: "module", ecmaFeatures: { jsx: true } },
  plugins: ["@typescript-eslint"],
  ignorePatterns: [
    "node_modules/**",
    "dist/**",
    "coverage/**",
    ".turbo/**",
    "playwright-report/**",
    "test-results/**",
    "docs-site/**",
    "**/tests/eslint/fixtures/**",
  ],
  rules: {
    "no-debugger": "error",
    "no-dupe-keys": "error",
    "no-unreachable": "error",
  },
};
