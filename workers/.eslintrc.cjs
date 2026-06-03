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
  ignorePatterns: ["node_modules/", "dist/", ".wrangler/"],
};
