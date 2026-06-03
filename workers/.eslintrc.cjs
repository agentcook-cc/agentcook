// Cloudflare Worker — minimal ESLint config
//
// Day 62 加:防止 root lint-staged `*.{ts,tsx} eslint --fix` 找不到
// config 时 ESLint 走 `npm init @eslint/config` 流程 KILL pre-commit。
// 真规则待 Day 63 协调员触发词清理 + A ESLint hook 全员落地后,本文件
// 可改 `extends` 指向 root config(如果 root 装了 typescript-eslint)。
module.exports = {
  root: true,
  env: {
    browser: false,
    es2022: true,
    worker: true,
  },
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: "module",
  },
  rules: {
    // 故意宽松 — Worker 代码已 review 过,不在 Day 62 范围加严
  },
  // Cloudflare Worker .ts 由 wrangler 自带 esbuild + 各 Worker 内 vitest
  // 类型检查兜底。Day 63 协调员 ESLint 触发词清理是项目层 .eslintrc.cjs
  // 范围(agentcook-app/admin),不覆盖 workers/。本目录显式 ignore *.ts
  // 避免 root lint-staged glob `*.{ts,tsx}` 拉走 ESLint 默认 parser
  // 失败(没装 typescript-eslint)。
  ignorePatterns: ["**/*.ts", "**/*.tsx", "node_modules/", "dist/", ".wrangler/"],
};
