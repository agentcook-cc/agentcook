# agentcook 前端开发规范(双栈)

> **文件状态**:v1 草稿(Day 8 主体,Day 9-10 续完)
> **作者**:Agent B(前端)
> **首次创建**:2026-05-18(Phase 1 Day 8)
> **适用范围**:`agentcook-admin`(Vue 3) / `agentcook-app`(React 18) / `agentcook-design-tokens`(共享)

---

## 0. 这份规范是什么

Phase 3(Day 26-37)admin + app 真正进入业务开发时,Agent B 自己执行的"宪法":每一个组件文件、每一条路由、每一行 API 调用都按这里写。Phase 5 教程章节 22-23 也会引用本规范作为"P7 工程化落地"的真凭据。

如果 Phase 3 写代码时发现某条规范"实战中走不通",**修这份规范**(回到 Day 8-10 的产出),不要在代码里偷偷开后门。

---

## 1. 总原则

### 1.1 双栈一致性优先

`admin` 是 Vue 3 + Element Plus 紧凑后台风,`app` 是 React 18 + Tailwind + shadcn/ui 现代消费风。**布局密度 / 组件库可以差异化**,但以下层面**必须双栈零认知差**:

- design-tokens 颜色 / 字体 / 间距(同一 token → 同一像素值)
- 错误码 / 错误文案
- 用户 / 权限模型
- API client 类型定义(从同一份 OpenAPI 生成)
- 一级菜单分类 / 业务术语
- 国际化 key 命名空间(`common.*` / `error.*` / `plugin.*` / `skill.*`)

### 1.2 Single Source of Truth

| 共享物 | 唯一信源 | 派生方 |
|--------|---------|--------|
| 设计 token | `agentcook-design-tokens/tokens/*.json` | admin / app / docs / Figma |
| API 类型 | `agentcook` 后端 OpenAPI v1(Day 24 冻结) | admin / app 通过 codegen |
| 错误码 | `agentcook-core/errors.py`(待 A 定) | 前端用工具脚本同步生成 enum |
| 业务术语 | `agentcook-design-tokens/docs/glossary.md`(Day 9 加) | i18n / UI 文案 / 教程 |

**反例**:admin 写一个"plugin"翻译成"插件",app 翻译成"扩展"——这是双栈不一致的典型违规。

### 1.3 No Premature Abstraction

Phase 3 写第 1 个 admin 页和第 1 个 app 页时,**不要**先抽 `useApi` / `useAuth` / `useFormState` 这种"通用 hook 库"。三处用到再抽,两处用到就重复。

---

## 2. 代码风格 — eslint / prettier / commit

### 2.1 Prettier(双栈共用)

根目录单一 `.prettierrc.json`,admin / app / design-tokens 共享:

```json
{
  "printWidth": 100,
  "tabWidth": 2,
  "useTabs": false,
  "semi": true,
  "singleQuote": true,
  "trailingComma": "es5",
  "bracketSpacing": true,
  "arrowParens": "always",
  "endOfLine": "lf"
}
```

**为什么 100 列**:Vue / TSX 的属性行常 80 列就要换行,90 列勉强,100 列舒服。再宽就影响 PR diff 横向滚动。

### 2.2 ESLint(双栈各自配置 + 共享 base)

ESLint 9+ flat config 形态。一份 base 抽到根目录,admin / app 各自 extends + 加 framework-specific 插件。

```
agentcook-cc/
├── eslint.config.base.mjs           ← 共享 base
├── agentcook-admin/eslint.config.mjs  ← extends base + Vue plugin
└── agentcook-app/eslint.config.mjs    ← extends base + React plugin
```

#### 2.2.1 共享 base — `eslint.config.base.mjs`

```js
// agentcook-cc/eslint.config.base.mjs
import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import importPlugin from 'eslint-plugin-import';
import promisePlugin from 'eslint-plugin-promise';
import unicornPlugin from 'eslint-plugin-unicorn';
import prettierConfig from 'eslint-config-prettier';

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  importPlugin.flatConfigs.recommended,
  importPlugin.flatConfigs.typescript,
  promisePlugin.configs['flat/recommended'],
  {
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      parserOptions: {
        project: true,                       // 自动找最近 tsconfig
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: { unicorn: unicornPlugin },
    rules: {
      // ─── TypeScript 严格度 ───────────────────────────
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      '@typescript-eslint/consistent-type-imports': ['error', { fixStyle: 'separate-type-imports' }],
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-non-null-assertion': 'warn',
      '@typescript-eslint/no-floating-promises': 'error',     // async 必 await / void / .then
      '@typescript-eslint/no-misused-promises': 'error',      // Promise 不能直接当 boolean 用
      '@typescript-eslint/await-thenable': 'error',
      '@typescript-eslint/no-unnecessary-type-assertion': 'error',
      '@typescript-eslint/prefer-nullish-coalescing': 'error',
      '@typescript-eslint/prefer-optional-chain': 'error',
      '@typescript-eslint/no-import-type-side-effects': 'error',
      '@typescript-eslint/no-unsafe-assignment': 'warn',
      '@typescript-eslint/no-unsafe-call': 'warn',
      '@typescript-eslint/no-unsafe-member-access': 'warn',
      '@typescript-eslint/restrict-template-expressions': ['error', { allowNumber: true, allowBoolean: true }],

      // ─── import 规范 ─────────────────────────────────
      'import/order': ['error', {
        groups: ['builtin', 'external', 'internal', 'parent', 'sibling', 'index', 'type'],
        'newlines-between': 'always',
        alphabetize: { order: 'asc', caseInsensitive: true },
        pathGroups: [
          { pattern: '@/**', group: 'internal', position: 'before' },
          { pattern: '@design-tokens/**', group: 'internal', position: 'before' },
        ],
      }],
      'import/no-cycle': ['error', { maxDepth: 3 }],
      'import/no-self-import': 'error',
      'import/no-useless-path-segments': 'error',
      'import/no-duplicates': 'error',
      'import/first': 'error',

      // ─── promise ────────────────────────────────────
      'promise/always-return': 'error',
      'promise/no-callback-in-promise': 'error',
      'promise/catch-or-return': 'error',

      // ─── 通用 JS ────────────────────────────────────
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      'no-debugger': 'error',
      'no-alert': 'error',
      'eqeqeq': ['error', 'always', { null: 'ignore' }],
      'curly': ['error', 'multi-line'],
      'no-var': 'error',
      'prefer-const': 'error',
      'prefer-template': 'error',
      'arrow-body-style': ['error', 'as-needed'],
      'no-implicit-coercion': 'error',
      'no-multi-assign': 'error',
      'no-nested-ternary': 'error',
      'no-restricted-syntax': ['error', { selector: 'TSEnumDeclaration', message: '用 const object + as const 替代 enum(避免运行时副作用)' }],

      // ─── unicorn 选用 ───────────────────────────────
      'unicorn/no-null': 'off',                    // 我们用 null 区分 "未加载" 和 "已加载但空"
      'unicorn/prefer-node-protocol': 'error',     // import 'node:fs' 不写 'fs'
      'unicorn/no-array-for-each': 'off',          // forEach 可读性比 for-of 好,允许
      'unicorn/prevent-abbreviations': 'off',      // props/refs 等约定俗成缩写允许

      // ─── 文件行数(双栈差异化,见 §4.3)─────────────────
      'max-lines': ['error', { max: 300, skipBlankLines: true, skipComments: true }],
    },
  },
  // 测试文件放宽 unsafe 系列(mock 数据常 any)
  {
    files: ['**/*.{test,spec,contract}.{ts,tsx}', '**/test/**', '**/__tests__/**'],
    rules: {
      '@typescript-eslint/no-unsafe-assignment': 'off',
      '@typescript-eslint/no-unsafe-call': 'off',
      '@typescript-eslint/no-unsafe-member-access': 'off',
      '@typescript-eslint/no-explicit-any': 'off',
      'max-lines': 'off',
    },
  },
  // codegen / generated 完全跳过
  {
    ignores: ['**/dist/**', '**/storybook-static/**', '**/api/generated/**', '**/*.gen.ts'],
  },
  prettierConfig,                                  // 关闭与 Prettier 冲突的风格 rule(最后一行很重要)
);
```

#### 2.2.2 admin override — Vue 3

```js
// agentcook-admin/eslint.config.mjs
import base from '../eslint.config.base.mjs';
import vuePlugin from 'eslint-plugin-vue';
import vueTsParser from 'vue-eslint-parser';

export default [
  ...base,
  ...vuePlugin.configs['flat/recommended'],
  {
    files: ['**/*.vue'],
    languageOptions: {
      parser: vueTsParser,
      parserOptions: { parser: '@typescript-eslint/parser', extraFileExtensions: ['.vue'] },
    },
    rules: {
      'vue/component-api-style': ['error', ['script-setup']],     // 强制 <script setup>
      'vue/component-name-in-template-casing': ['error', 'PascalCase'],
      'vue/define-macros-order': ['error', { order: ['defineProps', 'defineEmits'] }],
      'vue/no-undef-components': 'error',
      'vue/no-unused-refs': 'error',
      'vue/padding-line-between-blocks': 'error',
      'vue/prefer-separate-static-class': 'error',
      'vue/no-v-html': 'warn',                                   // 防 XSS,允许必要时 disable
      'max-lines': ['error', { max: 500, skipBlankLines: true, skipComments: true }],  // SFC 三段合计
    },
  },
];
```

#### 2.2.3 app override — React 19

```js
// agentcook-app/eslint.config.mjs
import base from '../eslint.config.base.mjs';
import reactPlugin from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import jsxA11y from 'eslint-plugin-jsx-a11y';

export default [
  ...base,
  reactPlugin.configs.flat.recommended,
  reactPlugin.configs.flat['jsx-runtime'],          // React 17+ 自动 import,不再要 import React
  jsxA11y.flatConfigs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    plugins: { 'react-hooks': reactHooks },
    settings: { react: { version: '19.0' } },
    rules: {
      'react/prop-types': 'off',                    // 用 TS 类型,不用 prop-types
      'react/jsx-uses-react': 'off',                // jsx-runtime 替代
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      'react/no-array-index-key': 'warn',
      'react/jsx-no-leaked-render': 'error',        // {x && <X/>} 当 x=0 渲染 0 的坑
      'react/jsx-no-useless-fragment': 'error',
      'jsx-a11y/no-autofocus': 'warn',              // autofocus 干扰键盘用户
      'jsx-a11y/click-events-have-key-events': 'error',
      'jsx-a11y/no-static-element-interactions': 'error',
      'max-lines': ['error', { max: 300, skipBlankLines: true, skipComments: true }],
    },
  },
];
```

**关键说明**:
- `recommendedTypeChecked` + `stylisticTypeChecked` 是 type-aware 规则,需要 `parserOptions.project`,所以装 ESLint 后必须先 `pnpm typecheck` 跑通,否则 lint 会报"找不到 project"
- `eslint-config-prettier` **必须放最后**,关掉与 Prettier 冲突的风格规则(否则 lint 和 prettier 互相打架)
- `noPropertyAccessFromIndexSignature` / `noUncheckedIndexedAccess` 在 tsconfig 已开(§3.1),ESLint 不需重复
- React 19:`jsx-runtime` 配置允许不写 `import React`

### 2.3 commit / pre-commit / commit-msg(monorepo scope)

工具栈:`lint-staged` + `simple-git-hooks` + `@commitlint/cli`(不引入 husky,体积更小 + 可控)。

#### 2.3.1 root `package.json` 完整配置

```jsonc
// agentcook-cc/package.json (跨 Agent 共享,Day 14-15 加;**改它要 cross-cutting flag**)
{
  "scripts": {
    "prepare": "simple-git-hooks",      // pnpm install 后自动注册 git hooks
    "lint": "turbo run lint",
    "lint:fix": "turbo run lint -- --fix",
    "lint:staged": "lint-staged --concurrent false"
  },
  "lint-staged": {
    "*.{ts,tsx,vue,js,mjs,cjs,json,md,yml,yaml}": "prettier --write",
    "agentcook-admin/**/*.{ts,vue}":      "eslint --fix --max-warnings=0",
    "agentcook-app/**/*.{ts,tsx}":        "eslint --fix --max-warnings=0",
    "agentcook-design-tokens/**/*.ts":    "eslint --fix --max-warnings=0",
    "agentcook/**/*.py":                  "ruff check --fix",
    "agentcook-core/**/*.py":             "ruff check --fix",
    "agentcook-providers/**/*.py":        "ruff check --fix",
    "agentcook-storage/**/*.py":          "ruff check --fix",
    "agentcook-java/**/*.java":           "spotless:apply"
  },
  "simple-git-hooks": {
    "pre-commit":  "pnpm lint:staged",
    "commit-msg":  "pnpm exec commitlint --edit $1"
  },
  "devDependencies": {
    "lint-staged":           "^15.2.0",
    "simple-git-hooks":      "^2.11.0",
    "@commitlint/cli":       "^19.0.0",
    "@commitlint/config-conventional": "^19.0.0",
    "prettier":              "^3.3.0"
  }
}
```

**关键**:
- `lint-staged` 按 glob 路径过滤(monorepo scope) — 改 admin 文件不会触发 app 的 ESLint,反之亦然,**速度可观**(单文件 commit 通常 < 2s)
- `--concurrent false`:避免多个 ESLint 实例同时占 typecheck 内存(monorepo + type-aware lint 内存开销不小)
- `--max-warnings=0`:lint warn 也卡 commit(一旦 warn 累积就难清),严格不留余地
- Python (ruff) / Java (spotless:apply) 同样走 lint-staged,**A/D 写后端时也享受**(跨 Agent 受益)
- `prepare` script:开发者 clone 后第一次 `pnpm install` 自动注册 git hooks,无需额外操作

#### 2.3.2 命令行钩子

| 钩子 | 命令 | 何时跑 | 失败影响 |
|------|------|--------|----------|
| `pre-commit` | `pnpm lint:staged` | `git commit` 前 | commit 被拒,需修后重 commit |
| `commit-msg` | `commitlint --edit $1` | commit message 写完后 | 同上;message 不符 angular convention 拒收 |

**不在钩子里跑**:
- `tsc` / `vitest` / `playwright` — 慢(动辄数秒),提交体验差;留给 CI 卡(Phase 5 Day 49)
- `pnpm build` — 同上
- `i18n:check` — 慢,留给 CI

#### 2.3.3 跳钩子(应急用,非常规)

```bash
git commit --no-verify -m "..."     # 跳 pre-commit + commit-msg
git commit -n -m "..."              # 同上
```

**仅在以下场景允许**:
- 紧急回滚生产事故(commit lint warn 拦不住已知必须的代码)
- 引入 lint 规则前的存量代码大批量 reformat commit

平时**不允许**;PR review 时如发现 `--no-verify` commit 没有合理 footer 标注 → 要求重做。

#### 2.3.4 monorepo 内 commit 演练

```bash
# 改 admin/src/views/PluginList.vue
git add agentcook-admin/src/views/PluginList.vue
git commit -m "feat(admin): PluginList 加批量启用按钮"
# → pre-commit:只对该文件跑 prettier + eslint(< 1s)
# → commit-msg:验 type=feat / scope=admin / subject 长度 OK
# → commit 成功

# 改了 design-tokens token JSON + admin 主题
git add agentcook-design-tokens/tokens/color.json agentcook-admin/src/styles/
git commit -m "feat(design-tokens): primary 补全 200/300/400/800/900"
# → pre-commit:design-tokens 跑 ESLint,admin 跑 prettier(只是 SCSS 没 ESLint 改,不影响)
# → commit-msg:scope=design-tokens 通过(scope-enum 列表内)
```

#### 2.3.5 给 A / C / D 的接口约定

我加 root `package.json` 的 `lint-staged` / `simple-git-hooks` 字段时,**Python 行(ruff)/ Java 行(spotless)是给 A / D 预留**。A 在 `agentcook-core` 加 ruff 配置后即生效;D 在 `agentcook-java` 加 `spotless-maven-plugin` 后即生效。**Day 14-15 我加这部分 root 配置时会 cross-cutting flag**。

### 2.4 commit message — Angular Conventional Commits

强制 [Angular convention](https://www.conventionalcommits.org/) 双 token:

```
<type>(<scope>): <subject>

[optional body]

[optional footer(s)]
```

#### type — 8 个(限定列表)

| type | 用途 | 例 |
|------|------|----|
| `feat` | 新功能 | `feat(app): chat SSE 流式响应` |
| `fix` | bug 修复 | `fix(admin): 401 拦截器死循环` |
| `refactor` | 不改行为的重构 | `refactor(core): SkillLoader 拆出 Plugin 解析` |
| `perf` | 性能优化 | `perf(app): chat 长列表虚拟滚动` |
| `test` | 测试改动 | `test(admin): PluginCard 删除流集成测` |
| `docs` | 文档(含 README / ADR) | `docs(conventions): §10 a11y 写完` |
| `chore` | 构建 / 依赖 / 配置 | `chore(deps): bump storybook 8.5 → 8.6` |
| `style` | 仅格式(prettier / 空格) | `style(app): prettier 全量 format` |

**禁止**:`update` / `improve` / `enhance`(语义模糊,挑 `feat`/`fix`/`refactor` 之一);CI 拒收。

#### scope — 9 个(monorepo 包级 + 横切)

| scope | 对应 |
|-------|------|
| `core` | `agentcook-core` |
| `providers` | `agentcook-providers` |
| `storage` | `agentcook-storage` |
| `admin` | `agentcook-admin` |
| `app` | `agentcook-app` |
| `design-tokens` | `agentcook-design-tokens` |
| `java` | `agentcook-java` 后端(ADR-013 引入)|
| `infra` | `.github/` / `deploy/` / `turbo.json` / `docker` / 部署横切 |
| `docs` | `tutorial/` / 顶层 ARCHITECTURE / ADR 文档 |

**多 scope 改动**:用最重的一个,正文里说清楚。例:

```
feat(app): chat SSE + 同步 admin Plugin 调用按钮

- app: SSE 流式 + token-by-token 渲染
- admin: PluginDetail 加 "立即调用" 按钮跳 app
```

**无 scope**:杂项可省 — `chore: 提升 node 到 20.18`(顶层升级);CI 允许 scope 为空。

#### subject

- 现在时第一人称("加" / "修" / "重构"),不写"已加" / "已修复"
- 全小写开头(scope 已大写视觉分隔)
- 不加句号
- 中文 / 英文都行,但**一个 PR 内保持一致**(本项目主中文)
- ≤ 50 字符(中文≈25 字)

#### CI 校验(commitlint)

`commitlint.config.mjs`:

```js
export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': ['error', 2, ['feat', 'fix', 'refactor', 'perf', 'test', 'docs', 'chore', 'style']],
    'scope-enum': ['warn', 2, ['core', 'providers', 'storage', 'admin', 'app', 'design-tokens', 'java', 'infra', 'docs']],
    'scope-empty': [2, 'never'],                 // 禁空 scope?— 可选,默认放宽允许空
    'subject-case': [0],                          // 中文不卡 case
    'header-max-length': [2, 'always', 72],
  },
};
```

接 simple-git-hooks `commit-msg` 钩子(见 §2.3)+ GitHub Actions PR title check(C 配)。

---

## 3. TypeScript 风格

### 3.1 tsconfig 三层结构 — `base` / admin / app

monorepo 共享一份严格 base,双栈各自 extends 加 framework-specific 选项。

#### 3.1.1 根 `tsconfig.base.json`(双栈 + design-tokens 共享)

```jsonc
// agentcook-cc/tsconfig.base.json (Day 14-15 加;改它要 cross-cutting flag)
{
  "compilerOptions": {
    /* ─── 编译目标 ─────────────────────────── */
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",            // 关键 — 不用 "node"/"node16",vite/turbopack 现代生态用 bundler
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "useDefineForClassFields": true,

    /* ─── 模块互操作 ─────────────────────────── */
    "esModuleInterop": true,
    "isolatedModules": true,                  // 单文件可独立编译,vite/swc 必须开
    "verbatimModuleSyntax": true,             // 5.0+,强制 import type — 配合 ESLint consistent-type-imports
    "resolveJsonModule": true,
    "allowImportingTsExtensions": false,      // 不允许 import './foo.ts'

    /* ─── strict 全套 ─────────────────────────── */
    "strict": true,                           // 一开全开:strictNullChecks / noImplicitAny / strictFunctionTypes / strictBindCallApply / strictPropertyInitialization / noImplicitThis / alwaysStrict / useUnknownInCatchVariables
    "noUncheckedIndexedAccess": true,         // arr[i] → T | undefined;数组 / map 默认必判空
    "noImplicitOverride": true,               // class override 必须显式 override 关键字
    "noPropertyAccessFromIndexSignature": true,  // record["foo"] vs record.foo 区分
    "noFallthroughCasesInSwitch": true,
    "exactOptionalPropertyTypes": true,       // { foo?: string } 不允许显式赋 undefined,只能省略 key

    /* ─── 输出 ─────────────────────────── */
    "noEmit": true,                           // 默认不生成 — 由 vite / tsup 处理产物;tsc 只做 typecheck
    "skipLibCheck": true,                     // 跳过 node_modules 的 .d.ts(否则 monorepo lib 互检爆慢)
    "forceConsistentCasingInFileNames": true,  // import 大小写敏感(防 Mac 写错 Linux 挂)

    /* ─── 路径 ─────────────────────────── */
    "baseUrl": ".",
    "paths": {
      "@design-tokens/*": ["agentcook-design-tokens/dist/*"]
    }
  }
}
```

#### 3.1.2 admin `tsconfig.json`

```jsonc
// agentcook-admin/tsconfig.json
{
  "extends": "../tsconfig.base.json",
  "compilerOptions": {
    "jsx": "preserve",                        // Vue 3 不需 JSX,但 .vue 文件内 TSX 可能用
    "types": ["vite/client", "element-plus/global"],
    "paths": {
      "@/*": ["src/*"],
      "@design-tokens/*": ["../agentcook-design-tokens/dist/*"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.tsx", "src/**/*.vue", "src/**/*.d.ts"],
  "exclude": ["node_modules", "dist"],
  "references": [{ "path": "./tsconfig.node.json" }]    // vite.config 单独编译
}
```

`tsconfig.node.json`:vite.config / scripts 用,target Node20,不参与 src 编译。

#### 3.1.3 app `tsconfig.json`

```jsonc
// agentcook-app/tsconfig.json
{
  "extends": "../tsconfig.base.json",
  "compilerOptions": {
    "jsx": "react-jsx",                       // React 17+ 自动 import,不写 import React
    "types": ["vite/client", "@tanstack/react-query"],
    "paths": {
      "@/*": ["src/*"],
      "@design-tokens/*": ["../agentcook-design-tokens/dist/*"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.tsx", "src/**/*.d.ts"],
  "exclude": ["node_modules", "dist"]
}
```

#### 3.1.4 design-tokens `tsconfig.json`(已存在,Day 7 写)

不 extends base(因为 stories 是 Storybook html-vite,不需要 React/Vue 类型) — 现状保留。

#### 3.1.5 关键选项的"为什么"

| 选项 | 不开就会怎样 |
|------|-------------|
| `noUncheckedIndexedAccess` | `arr[i].foo` 即使 i 越界也不报,运行时崩 |
| `verbatimModuleSyntax` | `import { type X, fn }` 混合 import,bundler 误把 type 打进运行时 bundle |
| `exactOptionalPropertyTypes` | `{ foo?: string }` 给 `{ foo: undefined }` 通过,后端 JSON 序列化把 undefined 真发出去 |
| `noPropertyAccessFromIndexSignature` | record 类型可任意 `.x` 访问,typo 不报 |
| `forceConsistentCasingInFileNames` | Mac 写 `import './Foo'` 实际文件 `foo.ts`,本地 OK 推 Linux CI 挂 |
| `skipLibCheck` | monorepo 装一堆库后,typecheck 慢到分钟级 |

### 3.2 类型导出

- 公共类型放 `src/types/`,按业务领域拆文件(`plugin.ts` / `skill.ts` / `connector.ts`)
- 不用 `interface` 也不用 `type` 一刀切的教条 — 对象形状用 `interface`(可被 augment),联合 / 工具类型用 `type`
- **API 类型不手写**,从 OpenAPI codegen(见 §7)

### 3.3 路径别名

> **修订(Day 10)**:旧版本写 `"@tokens": ["...css"]` 是 bug — TS `paths` 是模块解析别名,不能指向 `.css`。改为指向包目录,各资产分别引用。

```jsonc
// admin / app 各自 tsconfig.json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"],
      "@design-tokens/*": ["../agentcook-design-tokens/dist/*"]
    }
  }
}
```

使用方:

```ts
// CSS variables(走 vite resolve.alias,不走 tsc paths)
import '@design-tokens/css/variables.css';

// Tailwind preset(走 tsc paths)
import preset from '@design-tokens/tailwind/preset.js';

// SCSS map(走 vite scss 加载)
@use '@design-tokens/element-plus/theme.scss' as tokens;
```

`vite.config.ts` 同步配 `resolve.alias`(因为 vite 不读 tsc paths):

```ts
import { fileURLToPath } from 'node:url';
import path from 'node:path';

resolve: {
  alias: {
    '@': fileURLToPath(new URL('./src', import.meta.url)),
    '@design-tokens': path.resolve(__dirname, '../agentcook-design-tokens/dist'),
  },
}
```

**禁用** `../../../foo` 三层以上相对路径 — 用 `@/` 或 `@design-tokens/`。

---

## 4. 组件目录约定

### 4.1 admin(Vue 3 + Element Plus)

```
agentcook-admin/src/
├── main.ts
├── App.vue
├── router/
│   ├── index.ts                ← createRouter + 路由树
│   └── modules/                ← 按业务模块拆,自动收集
│       ├── plugin.ts
│       ├── skill.ts
│       ├── connector.ts
│       └── monitoring.ts
├── layouts/                     ← 页面外层框架(顶导 + 侧边栏 + 主内容 slot)
│   ├── AdminLayout.vue          ← 默认布局(侧边栏 + 顶部 + 内容)
│   ├── AuthLayout.vue           ← 登录 / 注册 / 忘记密码用(无侧边栏,居中卡片)
│   └── BlankLayout.vue          ← 401 / 403 / 404 / 5xx 错误页 + 全屏向导
├── views/                       ← 页面级组件,1 路由 = 1 view,在 layout slot 里渲染
│   ├── plugin/
│   │   ├── PluginList.vue
│   │   ├── PluginDetail.vue
│   │   └── PluginUpload.vue
│   └── ...
├── components/                  ← 可复用组件,3 处以上用到才进
│   ├── biz/                     ← 业务组件(知道 plugin/skill 模型)
│   └── common/                  ← 通用组件(纯 UI,不知业务)
├── composables/                 ← 组合式函数(useXxx)
│   ├── useAuth.ts
│   ├── useApi.ts
│   └── usePagination.ts
├── stores/                      ← Pinia stores,按业务拆
│   ├── auth.ts
│   ├── plugin.ts
│   └── ui.ts                    ← UI 状态(侧边栏折叠 / 主题)
├── api/                         ← API client(codegen 输出)
│   ├── generated/               ← orval / openapi-typescript 自动生成,禁手改
│   ├── client.ts                ← axios / fetch 实例 + 拦截器
│   └── index.ts                 ← 重新导出 generated 内容
├── locales/
│   ├── zh-CN.json
│   ├── en-US.json
│   └── index.ts
├── styles/
│   ├── element-plus.scss        ← 接入 design-tokens SCSS map
│   ├── reset.scss
│   └── transitions.scss
├── types/                       ← 业务类型(非 API 类型)
│   └── ...
└── utils/                       ← 纯函数工具(date / format / validation)
    └── ...
```

**核心约定**:
- `views/` 是路由叶子节点,一个 view = 一个 url
- `components/biz/` 知道业务,`components/common/` 不知业务(可复用到任何项目)
- `composables/` 命名 `use*`,返回 `ref` / `reactive` / 函数
- `stores/` 一个 store 一个 store(认证 / Plugin / UI 状态各自独立)
- 文件名:Vue 文件 PascalCase(`PluginList.vue`),其他 camelCase(`useAuth.ts`)

### 4.2 app(React 18 + Tailwind + shadcn/ui)

```
agentcook-app/src/
├── main.tsx
├── App.tsx
├── pages/                       ← 路由叶子,文件即 url(generouted 自动生成 src/router.gen.ts,无需手写 router/)
│   ├── _app.tsx                 ← 根 layout(全应用包一层 — providers / theme / i18n)
│   ├── _404.tsx                 ← 404
│   ├── (auth)/                  ← 路由分组,共享 AuthLayout(登录无侧边栏)
│   │   ├── _layout.tsx          ← AuthLayout(居中卡片)
│   │   ├── login.tsx
│   │   └── register.tsx
│   ├── (main)/                  ← 主应用分组,共享 MainLayout(侧边栏 + 顶部)
│   │   ├── _layout.tsx          ← MainLayout
│   │   ├── index.tsx            → /
│   │   ├── chat/[sessionId].tsx → /chat/:sessionId
│   │   └── settings/index.tsx   → /settings
├── components/
│   ├── biz/
│   │   ├── ChatMessageList.tsx
│   │   ├── PluginPicker.tsx
│   │   └── SkillCallCard.tsx
│   ├── ui/                      ← shadcn/ui primitive(npx shadcn add 来的,禁手改)
│   │   ├── button.tsx
│   │   ├── dialog.tsx
│   │   └── ...
│   └── common/                  ← 自己写的通用组件
├── hooks/                       ← React hooks(命名 use*)
├── stores/                      ← Zustand stores
├── api/
│   ├── generated/               ← codegen 输出
│   ├── client.ts                ← TanStack Query 配置 + fetch 拦截
│   └── queries/                 ← React Query hook 包装(usePluginsQuery 等)
├── locales/                     ← react-i18next + 同 admin 命名空间
├── styles/
│   ├── globals.css              ← Tailwind base + design-tokens 注入
│   └── tailwind.config.js       ← extends design-tokens preset
├── types/
└── utils/
```

**与 admin 的差异**:
- React 用 `pages/` 文件式路由(generouted),Vue 用 `views/` + `router/modules/` 显式声明
- shadcn/ui primitive 进 `components/ui/`,不进 `components/common/`(标记来源避免误改)
- React Query 的 hook 包装单独放 `api/queries/`,Vue 的 composable + Pinia 二合一在 `stores/` + `composables/`

### 4.3 双栈通用规则

- **文件行数上限**(差异化):
  - **Vue SFC**:**500 行**(template + script + style 三段合计),其中 `<script setup>` 块单独 ≤ **250 行**
  - **React TSX**:**300 行**(无 style 同文件)
  - 超限要么拆,要么显式 `// eslint-disable-next-line max-lines` + 注释说明为何不拆(罕见 — 例如生成的 react-flow 节点配置)
- 一个文件只 export 一个主组件 + 内部子组件可同文件(< 50 行的子组件不必另起文件)
- 组件 props 类型必须显式声明,不用 `props: any`
- 不在组件文件里写 fetch / axios 调用 — 走 `api/` 层
- ESLint `max-lines` rule 双栈各自配上限

---

## 5. 路由规范

### 5.1 URL 设计

```
/login                    登录
/                         首页(admin: dashboard / app: chat)
/plugins                  Plugin 列表
/plugins/:id              Plugin 详情
/plugins/new              新建
/skills                   Skill 列表
/skills/:id/edit          Skill 编辑
/connectors               Connector 列表
/connectors/:id/oauth     Connector OAuth 流程
/monitoring               监控(admin only)
/users                    用户管理(admin only)
/chat/:sessionId          对话(app only)
/settings                 设置
```

**约定**:
- 列表 = 复数(`/plugins`),详情 = 复数 + id(`/plugins/:id`)
- 操作动词 = 子路径(`/plugins/new` / `/plugins/:id/edit`)— 不用 query string `?action=new`
- 不用 hash 路由(`/#/plugins`)— 用 history mode,Cloudflare Pages SPA fallback

### 5.2 admin Vue Router 4

`router/modules/plugin.ts`:

```ts
import type { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/plugins',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { auth: true, title: 'Plugin 管理' },
    children: [
      { path: '', name: 'plugin-list', component: () => import('@/views/plugin/PluginList.vue') },
      { path: 'new', name: 'plugin-new', component: () => import('@/views/plugin/PluginUpload.vue') },
      { path: ':id', name: 'plugin-detail', component: () => import('@/views/plugin/PluginDetail.vue') },
    ],
  },
];
export default routes;
```

`router/index.ts` 自动收集 modules:

```ts
const modules = import.meta.glob<{ default: RouteRecordRaw[] }>('./modules/*.ts', { eager: true });
const routes = Object.values(modules).flatMap((m) => m.default);
```

### 5.3 app React Router 6 + generouted

文件式路由(`pages/chat/[sessionId].tsx` → `/chat/:sessionId`),少手写 routes 配置。

### 5.4 路由守卫 — 4xx / 5xx 全覆盖

> **决策依据**:B2 history 模式 + B3 双 token 鉴权(决策 1/3)。SPA fallback `/* /index.html 200`(Cloudflare Pages `_redirects` / nginx `try_files`)由 C 配。

#### 5.4.1 401 — 未登录 / token 失效

**触发**:进受保护路由 + auth store 无 user / accessToken;**或**任意 API 401 拦截器 refresh 失败。

**行为**:
1. **保留来源**:把当前 path + query 编码成 `?redirect=` 放进 `/login` URL
2. 跳 `/login?redirect=/plugins/123`
3. 登录成功后读 `redirect` query,跳回原页

```ts
// admin/src/router/guards.ts
router.beforeEach(async (to, from) => {
  const auth = useAuthStore();
  const requiresAuth = to.meta.auth !== false;          // 默认所有路由要登录,白名单写 meta.auth: false
  if (requiresAuth && !auth.isAuthed) {
    return { name: 'login', query: { redirect: to.fullPath } };
  }
});
```

```ts
// admin/src/views/auth/Login.vue 内成功 callback
const route = useRoute();
const redirect = (route.query.redirect as string) ?? '/';
router.replace(redirect);
```

#### 5.4.2 403 — 已登录但无权限

**触发**:进路由 + 用户 role 不在 `meta.roles` 列表;**或**API 返 403。

**行为**:
- 路由级:跳 `/403`(`AccessDeniedView.vue`,显示"你没有访问 X 的权限,联系管理员")
- API 级:全局 toast 红色 + 留在原页(不跳走 — 用户可能只是某个动作没权限,菜单整体能看)

```ts
router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.meta.roles && !to.meta.roles.some((r) => auth.user?.roles.includes(r))) {
    return { name: '403' };
  }
});
```

#### 5.4.3 404 — 路由不存在

**触发**:URL 不匹配任何 route;**或**资源详情 API 返 404(`/plugins/abc-not-exists`)。

**行为**:
- 路由级:Vue Router 通配 `path: '/:pathMatch(.*)*'` → `NotFoundView.vue`(显示"页面没找到 + 回首页 / 联系")
- 资源级:detail view 内捕获 404 → 渲染 inline NotFound block(不跳整页 — 保持侧边栏 + 顶导,用户能继续浏览其他)

```ts
// admin/src/router/index.ts(catch-all 必须放最后)
{ path: '/:pathMatch(.*)*', name: '404', component: () => import('@/views/error/NotFound.vue') }
```

#### 5.4.4 5xx — 后端错 / 网络错

**触发**:任何 API 返 500/502/503/504;**或**网络断(`navigator.onLine === false`)。

**行为**:
- 默认:全局 toast 红色"服务暂时不可用,请稍后重试"+ 留在原页
- 关键操作(支付 / 写入)失败:弹 Modal,提供"重试 / 取消" 双按钮
- 大面积 5xx(短时间 ≥ 3 次):显示全屏降级页 `/maintenance`(给运维一个"服务降级中"的喘息位置)

```ts
// customFetch 拦截器(§7.3)尾部
let consecutive5xx = 0;
instance.interceptors.response.use(
  (res) => { consecutive5xx = 0; return res; },
  (err) => {
    if (err.response?.status >= 500) {
      consecutive5xx++;
      if (consecutive5xx >= 3) {
        router.push('/maintenance');
      } else {
        showError(i18n.t('error.network.server'));
      }
    }
    return Promise.reject(err);
  },
);
```

#### 5.4.5 路由切换 loading 不阻塞

beforeEach 不要 `await` 拉数据 — 切换瞬间用户已经看到 layout,具体内容 loading skeleton 在视图组件内画。**禁止**在 beforeEach 里:

```ts
// ❌ 反例 — 切路由要等 1s 数据回来才显示
router.beforeEach(async (to) => {
  if (to.name === 'plugin-detail') {
    await api.plugins.get(to.params.id);   // 不要这样
  }
});

// ✅ 正例 — 切瞬间 layout 渲染,view 内 useQuery 自己处理 loading
// PluginDetail.vue
const { data, isLoading, error } = usePluginQuery(route.params.id);
```

#### 5.4.6 layout 选择(对接 §4.1 layouts/)

| 路由 | layout |
|------|--------|
| `/login` / `/register` / `/forgot-password` | `AuthLayout`(居中卡片) |
| `/plugins` / `/skills` / `/chat/*` 等正常业务 | `AdminLayout` / `MainLayout`(侧边栏 + 顶部) |
| `/401` / `/403` / `/404` / `/maintenance` | `BlankLayout`(全屏) |

```ts
// admin/src/router/index.ts
{
  path: '/',
  component: () => import('@/layouts/AdminLayout.vue'),
  children: [/* 业务路由 */],
},
{
  path: '/login',
  component: () => import('@/layouts/AuthLayout.vue'),
  children: [{ path: '', component: () => import('@/views/auth/Login.vue'), meta: { auth: false } }],
},
{
  path: '/:pathMatch(.*)*',
  component: () => import('@/layouts/BlankLayout.vue'),
  children: [{ path: '', component: () => import('@/views/error/NotFound.vue'), meta: { auth: false } }],
}
```

#### 5.4.7 Cloudflare Pages SPA fallback

```
# agentcook-admin/public/_redirects(C 配,Phase 4 部署)
/*  /index.html  200
```

nginx 等价(自托管时):

```nginx
location / {
  try_files $uri $uri/ /index.html;
}
```

**关键**:fallback 必须返 200(不是 404),否则浏览器视为 404 不会进 SPA 路由。

---

## 6. 状态管理约定

### 6.1 admin — Pinia 2

每个 store 一个文件,`defineStore` setup 风格:

```ts
// agentcook-admin/src/stores/auth.ts
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { api } from '@/api';                    // ← orval 生成的 client(§7.1)
import type { User } from '@/api/generated/schemas';

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null);
  const accessToken = ref<string | null>(null); // ← in-memory only,refresh cookie 由后端管(§7.3)
  const isAuthed = computed(() => user.value !== null);

  async function login(username: string, password: string) {
    const res = await api.auth.login({ username, password });
    user.value = res.user;
    accessToken.value = res.accessToken;
  }

  function setAccessToken(token: string) {
    accessToken.value = token;       // refresh 拦截器调
  }

  function logout() {
    user.value = null;
    accessToken.value = null;
  }

  return { user, accessToken, isAuthed, login, setAccessToken, logout };
}, {
  persist: {                          // 白名单 persist(决策 5)
    paths: ['user'],                  // accessToken 只在内存,不持久化
    key: 'agentcook:auth:v1',
  },
});
```

**不用 options 风格** — setup 风格和 `<script setup>` 一致,组合性更好。

### 6.2 app — Zustand + TanStack Query 二分法

**严格区分**:

- **Server state**(后端的真理):用 TanStack Query。pluginList / skillDetail / userInfo 这种"远端拉来的数据"全部 useQuery。**不要把 server state 塞进 zustand**。
- **Client state**(前端 own 的状态):用 zustand。侧边栏折叠 / 当前选中的 session id / 主题模式 / 输入框草稿。

```ts
// stores/ui.ts
import { create } from 'zustand';

interface UiState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  theme: 'light' | 'dark';
  setTheme: (t: 'light' | 'dark') => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  theme: 'light',
  setTheme: (theme) => set({ theme }),
}));
```

```ts
// api/queries/usePluginsQuery.ts
import { useQuery } from '@tanstack/react-query';
import { api } from '@/api';

export function usePluginsQuery() {
  return useQuery({
    queryKey: ['plugins'],
    queryFn: () => api.plugins.list(),
    staleTime: 30_000,
  });
}
```

**反模式**:在 zustand store 里写 `fetchPlugins()` action 把数据塞进 store —— 这是 Redux 时代遗毒,React Query 时代不用。

### 6.3 双栈共享原则

- 状态只在用到它的最近层 lift up,**不**预先全 global
- 表单状态用 vee-validate (admin) / react-hook-form (app),**不**进 store
- 国际化 / 主题 / 用户身份 = 全 global(分别走 i18n 实例 / theme provider / auth store)

### 6.4 命名规则(三类前缀,看名字就知道是哪类)

| 前缀 | 用途 | 例 |
|------|------|----|
| `use{Domain}Store` | zustand / Pinia store(client state) | `useUiStore` / `useAuthStore` / `useChatDraftStore` |
| `use{Domain}Query` / `use{Domain}Mutation` | TanStack Query / Vue Query(server state) | `usePluginsQuery` / `useDeletePluginMutation` |
| `use{Action}` | 自定义 hook / composable(逻辑复用) | `useDebouncedValue` / `useClickOutside` / `usePagination` |

**铁律**:
- store 后缀 **`Store`** 不能省(读代码时一眼看出是 zustand state)
- query / mutation 必须带后缀(避免和普通 hook 混)
- 自定义 hook 不带 `Store` / `Query` 后缀(避免误判)

### 6.5 持久化 — 白名单(决策 5)

只这三个 store 持久化,其余一律不:

| store | 持久化字段 | key | 工具 |
|-------|----------|-----|------|
| `useUiStore` | theme / sidebarCollapsed / lang | `agentcook:ui:v1` | pinia-plugin-persistedstate / zustand persist |
| `useAuthStore` | user(不含 accessToken) | `agentcook:auth:v1` | 同上 |
| `useChatDraftStore`(app)| 输入框未发送草稿 | `agentcook:chat:v1` | 同上 |

**禁止** TanStack Query 持久化(server state 失效后误用过期数据,陷阱多)。Day 14-15 P0-8 admin/app skeleton 落地时一并接入 persist 中间件。

---

## 7. API client 调用约定

> **决策依据**:B3(JWT 双 token:access in-memory 15min + refresh httpOnly cookie 7d)+ B6(orval 双栈 codegen)。

### 7.1 codegen 工具 — orval

**为什么 orval**(已拍板):双栈通吃 — 一份 `orval.config.ts` 同时输出 admin 的 Vue Query / Pinia 包装 + app 的 TanStack Query hooks,支持 Pact mock,maintainer 活跃。

`orval.config.ts`(根目录):

```ts
import { defineConfig } from 'orval';

export default defineConfig({
  // admin: axios + Vue Query 包装
  admin: {
    input: { target: './openapi.json' }, // 从 agentcook 后端 dump
    output: {
      mode: 'tags-split',                 // 按 OpenAPI tag 拆文件(plugin / skill / connector...)
      target: './agentcook-admin/src/api/generated',
      schemas: './agentcook-admin/src/api/generated/schemas',
      client: 'vue-query',
      httpClient: 'axios',
      override: {
        mutator: {
          path: './agentcook-admin/src/api/client.ts',
          name: 'customFetch',
        },
      },
    },
  },
  // app: TanStack Query + fetch
  app: {
    input: { target: './openapi.json' },
    output: {
      mode: 'tags-split',
      target: './agentcook-app/src/api/generated',
      schemas: './agentcook-app/src/api/generated/schemas',
      client: 'react-query',
      httpClient: 'fetch',
      override: {
        mutator: {
          path: './agentcook-app/src/api/client.ts',
          name: 'customFetch',
        },
      },
    },
  },
});
```

### 7.2 codegen 触发时机

| 时机 | 动作 | 触发 |
|------|------|------|
| 后端 OpenAPI 改 | A 在 `agentcook` 包 build CI 推 `openapi.json` 到 monorepo 根 | A 责任 |
| 前端本地开发 | `pnpm codegen` 手动触发 | B 责任 |
| CI(每次 PR) | 跑 `pnpm codegen --check`,如果生成结果与 git 不一致 → fail | C 责任 |
| Day 14-15 起 | `agentcook-core/errors.py` 错误码 enum **必须 Day 22 末冻结**,前端有 codegen 脚本同步 | A 责任,Day 22 deadline |

**禁手写 API client**。codegen 输出进 `api/generated/`,`.gitignore` 排除 → CI 重生成(避免 schema 漂移悄悄进 git)。

### 7.3 customFetch 拦截器(双栈共享逻辑)

orval 的 `mutator` 字段让我们把所有 codegen 出的请求都走自定义 `customFetch`,在这里实现 JWT 双 token 流。

**伪代码骨架**(admin / app 各 1 份,差异在底层 axios vs fetch):

```ts
// agentcook-admin/src/api/client.ts(app 版只换 axios → fetch + AbortController)
import axios, { type AxiosRequestConfig } from 'axios';
import { useAuthStore } from '@/stores/auth';

const baseURL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

const instance = axios.create({
  baseURL,
  withCredentials: true, // refresh cookie 自动带
  timeout: 30_000,
});

// 单一 refresh promise — 防雪崩(并发 401 不能各自调 /auth/refresh)
let refreshing: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  if (refreshing) return refreshing;
  refreshing = (async () => {
    try {
      const res = await axios.post('/auth/refresh', null, {
        baseURL,
        withCredentials: true,
      });
      const newAccess: string = res.data.access_token;
      useAuthStore().setAccessToken(newAccess);
      return newAccess;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

// 请求拦截:塞 access token + CSRF
instance.interceptors.request.use((config) => {
  const access = useAuthStore().accessToken;
  if (access) config.headers.Authorization = `Bearer ${access}`;
  // CSRF:从 cookie 读 csrf_token → 写 X-CSRF-Token header
  const csrf = readCookie('csrf_token');
  if (csrf && config.method !== 'get') {
    config.headers['X-CSRF-Token'] = csrf;
  }
  return config;
});

// 响应拦截:401 自动 refresh + 重试 1 次
instance.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config as AxiosRequestConfig & { _retry?: boolean };
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true; // 防无限循环
      try {
        await refreshAccessToken();
        return instance(original); // 用新 access 重试
      } catch (refreshErr) {
        // refresh 也 401 → cookie 过期,跳登录
        useAuthStore().logout();
        window.location.href = '/login';
        return Promise.reject(refreshErr);
      }
    }
    return Promise.reject(error);
  },
);

export const customFetch = async <T>(config: AxiosRequestConfig): Promise<T> => {
  const res = await instance.request<T>(config);
  return res.data;
};
```

**关键不变量**:
- access token **只在内存**(Pinia / Zustand store,15 分钟过期)— 刷新页面就丢,下次请求 401 → 自动 refresh
- refresh token **只在 httpOnly cookie**(`Domain=.agentcook.cc; Secure; SameSite=Lax; Max-Age=604800`)— JS 拿不到,XSS 偷不到
- CSRF token 在普通 cookie(JS 可读),double submit pattern,non-GET 必带 `X-CSRF-Token` header
- 401 → refresh → 重试只走一次(`_retry` 标记防循环)
- 并发 401 共享一个 refresh promise(`refreshing` 单例)防雪崩

### 7.4 错误码处理(全局 + 局部)

**错误码源**:`agentcook-core/errors.py` 定义的 enum,**Day 22 末必须冻结**(F-3 audit)。前端用脚本(Day 22 加)从 Python enum 同步生成 TS enum:

```ts
// generated/error-codes.ts
export enum ErrorCode {
  AUTH_INVALID_TOKEN = 'AUTH_INVALID_TOKEN',
  PLUGIN_NOT_FOUND = 'PLUGIN_NOT_FOUND',
  SKILL_EXEC_TIMEOUT = 'SKILL_EXEC_TIMEOUT',
  // ... 由 A 维护
}
```

**全局 toast**(default behavior):

```ts
// 在 customFetch 拦截器尾部
instance.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.data?.code) {
      const code = error.response.data.code as ErrorCode;
      // i18n 查 error.{code} key
      const msg = i18n.t(`error.${code}`, '未知错误');
      // 全局 toast(admin: ElNotification / app: sonner)
      showError(msg);
    }
    return Promise.reject(error);
  },
);
```

**业务局部覆盖**(组件内 try / catch 不走全局 toast):

```ts
try {
  await api.plugins.delete(id);
} catch (e) {
  if (isErrorCode(e, ErrorCode.PLUGIN_HAS_DEPENDENTS)) {
    // 业务自己处理 — 弹 dialog 让用户确认级联删除
    showDependentsDialog();
    return;
  }
  throw e; // 其他错误走全局
}
```

### 7.5 SSE 流式接入(chat / skill 在线测试)

orval 不直接生成 SSE,需手写。**双栈共享 SSE hook**:

```ts
// agentcook-app/src/api/sse.ts
export async function* streamChat(sessionId: string, message: string, signal?: AbortSignal) {
  const access = useAuthStore.getState().accessToken;
  const res = await fetch(`/api/v1/chat/${sessionId}/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${access}`,
    },
    body: JSON.stringify({ message }),
    credentials: 'include',
    signal,
  });
  if (!res.ok) {
    if (res.status === 401) {
      // SSE 没法触发 axios 拦截器,这里手动 refresh + 重试
      await refreshAccessToken();
      yield* streamChat(sessionId, message, signal);
      return;
    }
    throw new Error(`SSE failed: ${res.status}`);
  }
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // 标准 SSE 分隔:`data: {json}\n\n`
    const lines = buffer.split('\n\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      const data = line.replace(/^data:\s*/, '');
      if (data === '[DONE]') return;
      yield JSON.parse(data) as ChatChunk;
    }
  }
}
```

**消费方**(React 组件):

```tsx
const [chunks, setChunks] = useState<ChatChunk[]>([]);
const send = async () => {
  const ctrl = new AbortController();
  for await (const chunk of streamChat(sessionId, input, ctrl.signal)) {
    setChunks((prev) => [...prev, chunk]);
  }
};
```

**关键不变量**:
- SSE 的 401 不能走 axios 拦截器(SSE 不走 axios),手动 refresh + 递归重试一次
- 用户切换 session / 关闭页面要 `AbortController.abort()` 释放连接(后端也要支持 client_disconnect 检测)
- 长连接超时 60s 重连(SSE 重连标 `Last-Event-ID`,后端按 ID 续传 — 这是 Phase 2 Day 23 与 A 同步)

### 7.6 给后端的接口约束(Day 24 API spec 冻结要写进 OpenAPI)

A 写 `agentcook` FastAPI 时务必满足:
1. `/api/v1/auth/login` 返 `{access_token, expires_in}` + `Set-Cookie: refresh_token` httpOnly + `Set-Cookie: csrf_token`(普通 cookie)
2. `/api/v1/auth/refresh` 读 refresh cookie → 返新 access + 轮换新 refresh cookie(refresh token rotation 防重放)
3. `/api/v1/auth/logout` 清 httpOnly cookie + 清 csrf cookie
4. 所有错误返 `{code: 'AUTH_INVALID_TOKEN', message: '...', detail?: {...}}` JSON 形态
5. 所有列表分页参数统一 `?page=1&size=20`,响应 `{items, total, page, size}`
6. SSE endpoint 用 `text/event-stream`,每条消息 `data: <json>\n\n`,结束 `data: [DONE]\n\n`

Day 24 末与 A 验收 OpenAPI 时按上面 6 条对照。

---

### 7.7 双 API base — Python `agentcook` + Java `agentcook-java`(ADR-013 增补,Day 12 Phase 3 起生效)

> **背景**:ADR-013 引入 Java 后端 `agentcook-java` 承接业务域(用户 / 会话 / 连接器配置 / 权限),Python `agentcook` 专注 LLM/Agent 域(agent / memory)。前端**双源**消费,通过同一 access token 跨域鉴权。

#### 7.7.1 路由分配

| Domain | base path | 后端 | OpenAPI 源 | Owner |
|--------|----------|------|-----------|-------|
| Agent / LLM | `/api/v1/agent/*` | Python `agentcook` | `docs/api/v1.yaml` | A |
| 长短期记忆 | `/api/v1/memory/*` | Python `agentcook` | 同上 | A |
| Skill / Plugin / Connector 调用 | `/api/v1/skills/*` `/api/v1/plugins/*` | Python | 同上 | A |
| 用户 / 角色 / 权限 | `/api/v1/users/*` `/api/v1/permissions/*` | **Java** | `docs/java-api/v1.yaml` | D |
| 会话管理 | `/api/v1/sessions/*` | **Java** | 同上 | D |
| Connector 配置 / OAuth 凭证 | `/api/v1/connectors/*`(配置面) | **Java** | 同上 | D |
| 鉴权 / refresh / logout | `/api/v1/auth/*` | **Java**(签发 token,access secret + refresh DB)| 同上 | D |

**双源边界原则**:
- "AI 推理 + 状态相关" → Python(LLM 调用 / Agent 运行 / Memory 读写)
- "持久化业务实体 + 权限模型 + 事务一致性" → Java(用户体系 / 会话元数据 / 配置管理)
- Connector 一分为二:**配置面** Java(用户在 admin 配 OAuth)/ **调用面** Python(Agent 运行时实际拉数据)

#### 7.7.2 同源 vs 跨源部署

| 部署形态 | URL | 前端处理 |
|---------|-----|---------|
| **生产**(推荐):统一域名 + Cloudflare Workers 路由分发 | `app.agentcook.cc/api/v1/*` 路由 → `agentcook-py.internal` / `agentcook-java.internal` | 前端**只配一个** baseURL,后端按 path 前缀分流 |
| **dev**:双端口直跑 | Python: `localhost:8000`,Java: `localhost:8080` | 前端 vite proxy 把 `/api/v1/agent/*` 代理 8000,`/api/v1/users/*` 代理 8080 |
| **staging**:双子域 | `py.staging.agentcook.cc` + `java.staging.agentcook.cc` | 前端配两个 baseURL,各自走 |

vite dev proxy 示例:

```ts
// admin/vite.config.ts
server: {
  proxy: {
    '/api/v1/agent':       { target: 'http://localhost:8000', changeOrigin: true },
    '/api/v1/memory':      { target: 'http://localhost:8000', changeOrigin: true },
    '/api/v1/skills':      { target: 'http://localhost:8000', changeOrigin: true },
    '/api/v1/plugins':     { target: 'http://localhost:8000', changeOrigin: true },
    '/api/v1/users':       { target: 'http://localhost:8080', changeOrigin: true },
    '/api/v1/sessions':    { target: 'http://localhost:8080', changeOrigin: true },
    '/api/v1/connectors':  { target: 'http://localhost:8080', changeOrigin: true },
    '/api/v1/permissions': { target: 'http://localhost:8080', changeOrigin: true },
    '/api/v1/auth':        { target: 'http://localhost:8080', changeOrigin: true },
  },
}
```

**生产前端代码无差异**:同源部署后,前端代码里 `/api/v1/...` 直接写,不关心后端是 Python 还是 Java。

#### 7.7.3 orval 双源配置

```ts
// orval.config.ts(扩展 §7.1)
import { defineConfig } from 'orval';

export default defineConfig({
  // ─── Python 源:Agent / Memory / Skill / Plugin ───────────────
  'admin-py': {
    input: { target: './docs/api/v1.yaml' },        // A 出
    output: {
      mode: 'tags-split',
      target: './agentcook-admin/src/api/generated/py',
      schemas: './agentcook-admin/src/api/generated/py/schemas',
      client: 'vue-query',
      httpClient: 'axios',
      override: {
        mutator: { path: './agentcook-admin/src/api/client.ts', name: 'customFetch' },
      },
    },
  },
  'app-py': {
    input: { target: './docs/api/v1.yaml' },
    output: {
      mode: 'tags-split',
      target: './agentcook-app/src/api/generated/py',
      schemas: './agentcook-app/src/api/generated/py/schemas',
      client: 'react-query',
      httpClient: 'fetch',
      override: {
        mutator: { path: './agentcook-app/src/api/client.ts', name: 'customFetch' },
      },
    },
  },
  // ─── Java 源:User / Session / Connector / Auth / Permission ──
  'admin-java': {
    input: { target: './docs/java-api/v1.yaml' },   // D 出(Day 24 OpenAPI 冻结)
    output: {
      mode: 'tags-split',
      target: './agentcook-admin/src/api/generated/java',
      schemas: './agentcook-admin/src/api/generated/java/schemas',
      client: 'vue-query',
      httpClient: 'axios',
      override: { mutator: { path: './agentcook-admin/src/api/client.ts', name: 'customFetch' } },
    },
  },
  'app-java': {
    input: { target: './docs/java-api/v1.yaml' },
    output: {
      mode: 'tags-split',
      target: './agentcook-app/src/api/generated/java',
      schemas: './agentcook-app/src/api/generated/java/schemas',
      client: 'react-query',
      httpClient: 'fetch',
      override: { mutator: { path: './agentcook-app/src/api/client.ts', name: 'customFetch' } },
    },
  },
});
```

**消费方导入**:

```ts
// admin
import { useUsersQuery } from '@/api/generated/java/users/users';        // Java 源
import { useChatStreamQuery } from '@/api/generated/py/agent/agent';     // Python 源
```

`api/index.ts` 重新导出聚合:

```ts
// admin/src/api/index.ts
export * as agent from './generated/py/agent';
export * as memory from './generated/py/memory';
export * as skill from './generated/py/skills';
export * as plugin from './generated/py/plugins';
export * as user from './generated/java/users';
export * as session from './generated/java/sessions';
export * as connector from './generated/java/connectors';
export * as auth from './generated/java/auth';
```

业务侧只 `import { agent, user } from '@/api'`,**不需要关心是 Python 还是 Java 源**。

#### 7.7.4 JWT 跨栈鉴权

**关键**:**access token 同时被 Python 和 Java 验证**。两种实现路径:

| 方案 | 优点 | 缺点 | 推荐 |
|------|------|------|------|
| **A. 共享 secret(HMAC HS256)**| 简单,启动即用 | secret 泄露双栈一起完蛋 + secret 轮换协调难 | dev / Phase 1 |
| **B. JWKS 公钥分发(RS256 / ES256)**| Java 签发 → 公钥 endpoint(`/.well-known/jwks.json`)→ Python pull 公钥验签 + 缓存 + 自动轮换 | 配置复杂(密钥对管理) | **生产推荐**,Phase 2 Day 23 切到 |

**B 方案下的工作流**(给 A / D 同步):

```
1. Java 启动 → 加载 RSA 私钥(从 K8s Secret 挂载)→ 暴露 /.well-known/jwks.json 公钥 endpoint
2. 用户登录 → Java /api/v1/auth/login 用 RS256 私钥签 JWT(payload: { sub, roles, exp }) → 返前端 + 写 refresh cookie
3. 前端调 Python `/api/v1/agent/*` 带 Bearer JWT
4. Python(FastAPI)启动时从 JWKS endpoint 拉公钥缓存(10min TTL)→ 收请求时用公钥验签
5. 公钥轮换:Java 加新 kid 进 JWKS → Python TTL 后自动拉到 → 平滑切换无 downtime
```

**前端不感知** — 前端只管把 access token 塞进 Authorization header(§7.3),双栈各自验。

#### 7.7.5 错误码统一

**约定**:Python 和 Java 共享同一个错误码 enum 命名空间(`agentcook-core/errors.py` 是源,Java 通过 codegen 同步;前端走 i18n `error.{code}` key,§7.4 / §8.8)。

**Day 22 末错误码冻结时,A 和 D 必须用同一份 enum**(D 在 Java 实现里 import `ErrorCode.AUTH_INVALID_TOKEN` 等,常量值与 Python 的 `errors.AUTH_INVALID_TOKEN.value` 字符串一致)。

#### 7.7.6 监控 / trace 串联

跨栈调用(前端 → Java auth → Python agent)要 OpenTelemetry trace context 传播:

- 前端发请求时塞 `traceparent` header(B + C 在 Phase 2 Day 23 接入 OTel-js)
- Java 收到 → 继承 trace → 调 Python 时透传 `traceparent`
- Python 继承 → Langfuse 关联 LLM trace
- Jaeger UI 可看到完整跨栈调用链

**前端责任**:Day 23 把 OTel browser SDK 接到 customFetch 拦截器,自动 inject `traceparent`。具体配合 C 在 Phase 2 Day 23 落地。

---

> **§7.7 整体落地节奏**:Day 12 文档先就位(给作者 / D / A 对齐边界);Day 24 末 D 出 `docs/java-api/v1.yaml` → orval 真生成 Java client;Day 23 OTel 跨栈 trace 接入;Phase 3 Day 26+ admin/app 真消费。**Day 12 不写 codegen 真产物**(yaml 没出),仅文档约定。

---

## 8. i18n 约定

> **决策依据**:B1(zh-CN 默认 + en-US 兜底,i18next 系,navigator.language 自动检测,zustand persist 用户偏好)。

### 8.1 工具

- **admin**:`vue-i18n@^9` + `@intlify/unplugin-vue-i18n`(编译时优化 / lazy load)
- **app**:`react-i18next@^14` + `i18next-browser-languagedetector`
- **共享 locale 文件格式**:JSON,key 命名空间扁平嵌套(双栈各自工具都吃)

### 8.2 文件结构(双栈共享 locale 内容)

```
agentcook-cc/
├── locales/                          ← Day 14-15 加,双栈共享原文 + 翻译
│   ├── zh-CN/
│   │   ├── common.json               ← 通用按钮 / 表单 / 状态文案
│   │   ├── error.json                ← 错误码翻译(key = ErrorCode enum)
│   │   ├── plugin.json
│   │   ├── skill.json
│   │   ├── connector.json
│   │   ├── chat.json
│   │   └── auth.json
│   └── en-US/
│       └── ... (同结构)
├── agentcook-admin/src/locales/      ← admin 特有翻译(管理端术语)
│   ├── zh-CN/admin.json
│   └── en-US/admin.json
├── agentcook-app/src/locales/        ← app 特有翻译(用户端术语)
│   ├── zh-CN/app.json
│   └── en-US/app.json
```

**双栈共享 + 各自补充**:`common` / `error` / `plugin` / `skill` 等业务通用 key 进根 `locales/`(zh / en 双语),admin / app 特有 key 进各自 `src/locales/`。打包时合并:

```ts
// admin/src/locales/index.ts
import zhShared from '../../../locales/zh-CN/index.ts'; // glob import
import zhAdmin from './zh-CN/admin.json';
const zhCN = { ...zhShared, admin: zhAdmin };
```

### 8.3 key 命名约定

```
{domain}.{feature}.{element}

✅ 正例:
plugin.list.title            → "插件列表"
plugin.list.empty            → "还没有插件,去市场看看"
plugin.upload.dragHint       → "拖拽 zip 文件到此处"
error.AUTH_INVALID_TOKEN     → "登录已过期,请重新登录"
common.button.confirm        → "确定"
common.button.cancel         → "取消"

❌ 反例:
plugin_list_title            (用 . 不用 _)
PluginListTitle              (camel/Pascal 不用)
"插件列表" (key)              (英文 key,值才是翻译)
```

**禁止**:
- 在组件内硬编码中文 / 英文文案 — 全走 i18n key
- 把 `t('xxx')` 拼接业务字符串(`t('common.delete') + ' ' + name`)— 用插值 `t('plugin.delete', { name })`

### 8.4 自动检测 + 持久化

**首次访问**:`navigator.language` → 匹配 `zh-CN` / `zh-*`(回退 zh-CN)/ 其他(回退 en-US)。

**用户切换**:UI 设置面板 select language → 写 `useUiStore.setLang('zh-CN' | 'en-US')` → zustand persist 自动写 localStorage(key: `agentcook:ui:v1`)。

**优先级**(从高到低):
1. localStorage 持久化偏好(用户主动设过就尊重)
2. URL `?lang=` query(用于分享链接强制切语言)
3. `navigator.language` 自动检测
4. 默认 `zh-CN`

```ts
// admin/src/i18n/index.ts
import { createI18n } from 'vue-i18n';
import { useUiStore } from '@/stores/ui';

function detectLocale(): 'zh-CN' | 'en-US' {
  const persisted = useUiStore.getState?.()?.lang; // SSR-safe
  if (persisted) return persisted;
  const urlLang = new URLSearchParams(location.search).get('lang');
  if (urlLang === 'zh-CN' || urlLang === 'en-US') return urlLang;
  const nav = navigator.language;
  return nav.startsWith('zh') ? 'zh-CN' : 'en-US';
}

export const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: 'en-US',
  messages,
});
```

### 8.5 i18n 路由策略(F-10 落地)

**默认**:URL **不带 lang**(`/plugins` 而不是 `/zh/plugins`)。语言通过 i18n store 切换,用户级偏好 zustand persist 跨 session 保留。

**例外**:`demo.agentcook.cc` landing 页用 `/zh` / `/en` 子路径(SEO 友好,Cloudflare 按子路径分流);admin / app 不需要 SEO,内部应用,简洁 URL 优先。

`?lang=` query 仅作为"分享链接强制切语言"通道(`/plugins?lang=en` 让英文用户分享给中文同事时强制中文)。

### 8.6 复数 / 占位符 / 富文本

```jsonc
// 占位符(双语都支持)
"plugin.deleteConfirm": "确定删除「{name}」吗?",
"plugin.deleteConfirm" (en): "Delete plugin \"{name}\"?",

// 复数(i18next ICU 语法)
"chat.messageCount": "{count} 条消息",
"chat.messageCount" (en): "{count, plural, one {# message} other {# messages}}",

// 富文本(链接 / 加粗)— 用 t-tag(react)/ <i18n-t> 组件(vue),不要 v-html
<i18n-t keypath="plugin.docs.help">
  <template #link>
    <RouterLink to="/docs/plugin">查看文档</RouterLink>
  </template>
</i18n-t>
```

### 8.7 翻译协同流程

| 场景 | 流程 |
|------|------|
| 写新功能 | 先在 zh-CN/{module}.json 加 key + 中文,**en-US 留 TODO 占位**,PR 走 |
| CI 校验 | `pnpm i18n:check` 脚本(Day 14-15 加)— 扫描 zh-CN keys 和 en-US keys 是否对齐,缺失 fail PR |
| 翻译 | Phase 5 Day 52-53 集中过一遍 en-US,作者 / 译者补全(英文版破圈用) |

### 8.8 给后端的约束

`error.{code}` key 必须和 `agentcook-core/errors.py` enum 名一致(F-3 提到的同步脚本会自动生成 zh-CN 占位 + 英文翻译占位)。A Day 22 末错误码 enum 冻结时,B 同步生成 `error.json` 骨架。

---

## 9. design-tokens 接入

> **⚠ Day 11 警告**:本节 §9.1 SCSS map / §9.2 Tailwind preset 的样例代码是 **Day 14-15 P0-5/P0-6 完善 SD adapter 后的目标态**。当前 SD `scss/variables` / `javascript/module` format 输出形态与样例不一致(详见 `_internal/audit/design-tokens-gaps.md` P0-5/P0-6)。
>
> **Day 11-13 admin/app 早期接入用 §9.3 CSS variables 直接消费 fallback 路径**,Phase 3 Day 26+ adapter 完善后切到 §9.1/§9.2 完整方案。

### 9.1 admin Element Plus

入口 `main.ts` import CSS variables:

```ts
import '@agentcook-cc/design-tokens/dist/css/variables.css';
import './styles/element-plus.scss';
```

`styles/element-plus.scss`:

```scss
@use '@agentcook-cc/design-tokens/dist/element-plus/theme.scss' as tokens;
@use 'element-plus/theme-chalk/src/index.scss' as * with (
  $colors: (
    'primary': (
      'base': tokens.$color-primary-500,
    ),
    // ... Day 14-15 完善
  )
);
```

### 9.2 app Tailwind

`tailwind.config.js`:

```js
import preset from '@agentcook-cc/design-tokens/dist/tailwind/preset.js';

export default {
  presets: [preset],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
};
```

`styles/globals.css` 同时 import CSS variables(让非 Tailwind 场景也能用 `var(--color-primary-500)`):

```css
@import '@agentcook-cc/design-tokens/dist/css/variables.css';
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### 9.3 不直接写色值 / 字号 / 间距字面量

```vue
<!-- ❌ 反例 -->
<div style="color: #3b82f6; padding: 16px;">...</div>

<!-- ✅ admin 正例 -->
<div class="text-primary p-4">...</div>

<!-- ✅ app 正例(Tailwind) -->
<div className="text-primary-500 p-4">...</div>
```

CSS variables 直接消费:

```css
.custom-btn {
  background: var(--color-primary-500);
  border-radius: var(--radius-md);
  padding: var(--spacing-2) var(--spacing-4);
  transition: transform var(--motion-duration-normal) var(--motion-easing-out);
}
```

---

## 10. a11y 约定

> **基线**:WCAG 2.1 AA。任何 PR 引入新组件 / 页面前必须自查本节。Phase 5 Day 49 配合 Agent C 跑 axe-core CI 全量回归。

### 10.1 颜色对比度

| 对象 | 最小对比度 | 工具自查 |
|------|----------|---------|
| 正文(< 18px) | 4.5:1 | Storybook addon-a11y(已加 Day 7)|
| 大字(≥ 18px / ≥ 14px bold)| 3:1 | 同上 |
| 图标 + 边框 + UI 控件 | 3:1 | 同上 |
| 失能态(disabled) | 不强制(WCAG 例外),但**视觉不能太弱** — 目标 ≥ 2.5:1 | 人眼 |

**与 design-tokens 对接**:Day 14-15 加 semantic 层(P0-2)后,所有 `text.*` / `bg.*` 组合都会预先 4.5:1 校验,组件直接用语义 token 不需自己算对比度。Phase 5 Day 49 跑 axe-core 全量校验。

### 10.2 focus 必须可见

**铁律**:任何可聚焦元素(button / a / input / [tabindex])在键盘聚焦时必须有 ≥ 3px、对比度 ≥ 3:1 的视觉边界。

```css
/* ❌ 禁止 */
button:focus { outline: none; }

/* ✅ 默认 — 浏览器原生 outline 已合规,不要去掉除非有替代 */
button:focus-visible {
  outline: 2px solid var(--color-primary-500);
  outline-offset: 2px;
}
```

Day 14-15 P2-5 加 `shadow-focus-ring` token(`0 0 0 3px var(--color-primary-500)/0.5`),双栈表单聚焦统一走它。

**禁止用 `:focus`**(鼠标点击也会触发,产生不必要 ring) — 一律用 `:focus-visible`(只对键盘聚焦)。

### 10.3 键盘导航 — 5 条铁律

1. **所有交互必须键盘可达** — 鼠标能点的,Tab + Enter / Space 也能触发。**禁止**只绑 `onClick` 给非 button / a 元素(`<div onClick>` 用 `<button>` 替代)
2. **Tab 顺序 = 视觉顺序** — DOM 顺序就是 Tab 顺序;如视觉顺序与 DOM 不同(flex / grid 重排),用 `tabindex` 矫正,但代价高,优先调 DOM
3. **Esc 关弹窗** — Modal / Drawer / Popover / Dropdown 一律支持 Esc 关闭(Element Plus / Radix 默认已支持,自写组件要补)
4. **Enter / Space 在 button 上等价** — 自定义 button-like 组件要同时绑(`<div role="button" tabindex="0" onKeyDown={handleEnterAndSpace}>`)
5. **focus trap 在弹窗里** — Modal 打开后 Tab 不能跑到背景元素;关闭时 focus 回到打开按钮(Radix `Dialog` / Element Plus `el-dialog` 默认已做,自写要用 `focus-trap-react` / `vue-focus-trap`)

### 10.4 aria 与语义 HTML

**优先级**:语义 HTML > aria > tabindex hack。

```html
<!-- ✅ 语义 HTML — screen reader 自动识别 -->
<button onClick={save}>保存</button>
<nav>...</nav>
<main>...</main>
<form><label for="email">邮箱</label><input id="email" /></form>

<!-- ⚠ 必要时用 aria 补语义,但能用语义 HTML 优先 -->
<div role="button" tabindex="0" aria-label="保存" onKeyDown={...}>保存</div>

<!-- ❌ 反例 — div 当 button 又不补 a11y -->
<div onClick={save}>保存</div>
```

**常用 aria 属性 cheatsheet**:

| 属性 | 用途 | 示例 |
|------|------|------|
| `aria-label` | 无文字按钮(图标 button)的语义 | `<button aria-label="关闭">×</button>` |
| `aria-labelledby` | 引用其他元素作为 label | `<dialog aria-labelledby="title-id">` |
| `aria-describedby` | 引用其他元素作为补充描述(error 提示)| `<input aria-describedby="email-err">` |
| `aria-live` | 动态内容通知 screen reader | `<div aria-live="polite">2 条新消息</div>` |
| `aria-current` | 标记当前页 / 步骤 | `<a aria-current="page">/plugins</a>` |
| `aria-expanded` | 折叠态 | `<button aria-expanded="true">详情</button>` |
| `aria-hidden` | 隐藏装饰元素(纯视觉)| `<svg aria-hidden="true">...</svg>` |

**aria-live 优先级**:
- `aria-live="polite"` — 等读完当前内容再报(toast / 异步加载完成)
- `aria-live="assertive"` — 立刻打断报(错误 / 重要警告,慎用)
- `aria-live="off"`(默认) — 不报

### 10.5 表单 a11y

```vue
<!-- admin Element Plus(已默认 a11y,但用法对才生效)-->
<el-form ref="formRef" :model="form" :rules="rules">
  <el-form-item prop="email" label="邮箱">
    <!-- el-form-item 自动关联 label + aria-required + aria-invalid + aria-describedby (error msg) -->
    <el-input v-model="form.email" type="email" autocomplete="email" />
  </el-form-item>
</el-form>
```

```tsx
// app(shadcn/ui Form 包了 react-hook-form,Radix Form 实现 a11y)
<Form {...form}>
  <FormField
    control={form.control}
    name="email"
    render={({ field }) => (
      <FormItem>
        <FormLabel>邮箱</FormLabel>           {/* htmlFor + id 自动关联 */}
        <FormControl><Input type="email" autoComplete="email" {...field} /></FormControl>
        <FormDescription>登录用</FormDescription>
        <FormMessage />                       {/* 自动 aria-describedby */}
      </FormItem>
    )}
  />
</Form>
```

**铁律**:
- 每个 `<input>` 必须有关联 `<label>`(`<label for="x">` 或包裹)
- error 必须 aria-describedby 关联
- required 加 `required` + 视觉星号,但不要只用星号(screen reader 听不到星号,加 `aria-label="必填"` 或在 label 文字写)
- autocomplete 属性按 [HTML autocomplete spec](https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#autofill) 给(密码管理器才能正确填)

### 10.6 用户偏好(prefers-* 媒体查询)

```css
/* 减少动效 — 前庭功能障碍 / 晕动症用户 */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}

/* 高对比度模式 */
@media (prefers-contrast: more) {
  :root {
    --color-text-primary: black;
    --color-bg-canvas: white;
    --color-border-default: black;
  }
}

/* 暗色模式(Phase 2 Day 22-23 接入,见 design-tokens-gaps.md P1-1)*/
@media (prefers-color-scheme: dark) {
  :root { /* 注入 dark token map */ }
}
```

### 10.7 第三方组件库的 a11y 现状

| 库 | a11y 默认 | 须额外做 |
|---|---|---|
| **Element Plus 2.7+**(admin) | 大多数组件 a11y 默认开 | `el-icon` 装饰图标加 `aria-hidden="true"`;自写复杂 widget 自检 |
| **Radix UI**(app shadcn/ui 底层) | a11y 行业标杆,默认完整 | shadcn/ui 添加新组件时不要改 Radix 内部 props |
| **TanStack Table**(列表)| 默认中等 | 排序按钮加 `aria-sort` |
| **echarts**(监控图表) | 图表 a11y 弱 | 图表外加 `<table>` 数据备份(给 screen reader 用)+ `role="img" aria-label="..."` |

### 10.8 工具链

- **开发时**:Storybook addon-a11y(已加 Day 7,axe-core 跑在每个 story)+ 浏览器 DevTools Lighthouse a11y 标签
- **CI**(Phase 5 Day 49):axe-playwright 集成进 Playwright e2e — 5 个核心流跑完 a11y 全量
- **生产监控**:Web Vitals + Cloudflare Analytics(无 a11y 直接监控,靠用户反馈 + 季度 audit)

### 10.9 自检 checklist(每写新组件前过一遍)

- [ ] 颜色对比度 ≥ 4.5:1(正文)/ 3:1(大字 + 图标)
- [ ] 键盘 Tab 能到 + 视觉 focus ring 可见
- [ ] Enter / Space 在 button-like 元素等价
- [ ] Modal / 弹窗 Esc 可关 + focus trap + 关闭后 focus 回归
- [ ] 图标 button 有 `aria-label`
- [ ] 表单 label / error / required 关联齐全
- [ ] 装饰图标 `aria-hidden="true"`
- [ ] 动态内容(toast / async result)有 `aria-live`
- [ ] 不用 `outline: none` 不补替代
- [ ] 测试在键盘 only(拔鼠标)走完核心流

---

## 11. 测试

> **基线**:对应 ADR-007 4 层测试金字塔。Phase 1 起单测就位,Phase 2 Day 24 后契约测试启用,Phase 3 e2e 写满,Phase 5 Day 48-49 总跑全链。

### 11.1 4 层金字塔比例

```
       ▲
      / \           5%   e2e (Playwright)
     /---\
    /     \         15%  契约 (Pact + msw)
   /-------\
  /         \       30%  集成 (Vue Test Utils / @testing-library)
 /-----------\
/             \     50%  单测 (vitest)
```

| 层 | 工具 | 跑得快 | 跑得稳 | 覆盖率目标 |
|---|---|---|---|---|
| 单元 | vitest | <50ms / 用例 | 95%+ | **≥ 80% 行覆盖** |
| 集成 | vitest + Vue Test Utils / @testing-library/react + msw | 100-500ms | 90%+ | 关键路径 100% |
| 契约 | Pact-js(consumer)+ msw fixture | 1s 级 | 95%+ | API 契约 100% |
| e2e | Playwright(C Day 7-8 已配)| 5-30s / 流 | 80%+ | 5 核心用户流程 |

### 11.2 文件位置 / 命名 / 共存

```
agentcook-admin/src/
├── components/biz/PluginCard.vue
├── components/biz/PluginCard.test.ts        ← 同目录共存 — 改组件时眼睛能看到测试
├── composables/usePagination.ts
├── composables/usePagination.test.ts
├── api/queries/usePluginsQuery.ts
└── api/queries/usePluginsQuery.contract.ts  ← Pact 契约测试

agentcook-cc/e2e/                            ← e2e 用例顶层(C 已建)
├── fixtures/
│   └── auth.ts                              ← 共享 fixture(登录态等)
├── auth.spec.ts                             ← 流 1:登录 / 注册 / 登出
├── plugin.spec.ts                           ← 流 2:Plugin 浏览 / 上传 / 启用
├── skill.spec.ts                            ← 流 3:Skill 浏览 / 调用 / 测试
├── chat.spec.ts                             ← 流 4:对话 / SSE / 多轮
└── multi-agent.spec.ts                      ← 流 5:Multi-Agent 流可视化
```

**约定**:
- 单测 / 集成测:`*.test.ts(x)` / `*.spec.ts(x)` 二选一(选 `.test`,与 vitest 默认对齐)
- Pact 契约:`*.contract.ts`(扩展名区分,跑命令也分开)
- e2e:全在 `agentcook-cc/e2e/` 顶层,不混进各 package

### 11.3 vitest 单测

**已跑通**(Day 8 起 design-tokens 内有 `tests/tokens.test.ts`,C 加的 vitest.config.ts)。admin / app 各自加 vitest.config.ts(继承根 base)。

**写测的优先级**:
1. **纯函数 / utility**:必须 100% 覆盖(date / format / validation / 业务计算逻辑)
2. **composable / hook**:核心逻辑必测(useAuth / usePagination 等)
3. **store**:必测(action 改 state 是否符合预期)
4. **组件**:**只测包含分支逻辑或可见副作用的**(简单展示组件不强测,集成测覆盖)

**反模式**(浪费时间):
- 测组件 props 渲染对(快照测试满天飞 — 改一个 css 全部 fail)
- 测 third-party 库的内部行为(测 vue-router 的 push 动作 — 那是它的事)
- 测 i18n key 是否存在(应该走 i18n CI 校验,不走单测)

### 11.4 集成测试

```ts
// admin: components/biz/PluginCard.test.ts
import { mount } from '@vue/test-utils';
import { createTestingPinia } from '@pinia/testing';
import PluginCard from './PluginCard.vue';

it('点删除按钮 → 弹确认对话框 → 确认后调 api.plugins.delete', async () => {
  const wrapper = mount(PluginCard, {
    props: { plugin: mockPlugin },
    global: { plugins: [createTestingPinia()] },
  });
  await wrapper.find('[data-testid="delete-btn"]').trigger('click');
  // 验证对话框出现
  expect(wrapper.find('[role="dialog"]').exists()).toBe(true);
  // 模拟确认
  await wrapper.find('[data-testid="confirm-btn"]').trigger('click');
  // 验证 API 被调用 — 但用 msw fixture 而不是 vi.mock
  expect(mockApi.plugins.delete).toHaveBeenCalledWith(mockPlugin.id);
});
```

**msw 是关键**(双栈共享 mock 服务):
- `agentcook-cc/test/msw/handlers.ts` — 一份 handler,admin / app / e2e 三处共享
- 改后端 API 形态 → 改 handler → admin / app / e2e 一起反映

### 11.5 Pact 契约测试(Day 24 起启用)

**消费端**(admin / app):

```ts
// admin/api/queries/usePluginsQuery.contract.ts
import { PactV3 } from '@pact-foundation/pact';

const provider = new PactV3({ consumer: 'agentcook-admin', provider: 'agentcook-backend' });

it('GET /api/v1/plugins 返回 plugin list', async () => {
  await provider
    .given('there are 2 plugins')
    .uponReceiving('a plugin list request')
    .withRequest({ method: 'GET', path: '/api/v1/plugins' })
    .willRespondWith({ status: 200, body: { items: [...], total: 2 } });

  await provider.executeTest(async (mockServer) => {
    const data = await api.plugins.list({ baseURL: mockServer.url });
    expect(data.items).toHaveLength(2);
  });
});
```

**生成的 pact.json** → C 推到 Pact Broker → A 后端 CI 拉下来跑 provider verification。

### 11.6 Playwright e2e — 5 核心用户流

| # | 流 | 关键 step | a11y 同步校验 |
|---|---|---------|--------------|
| 1 | 登录 / 注册 / 登出 | 注册 → 邮箱验证 → 登录 → token 刷新 → 登出 | axe 跑登录页 |
| 2 | Plugin 上传 → 启用 → 调用 | 上传 zip → 沙箱启动 → 在 chat 里 invoke | axe 跑 Plugin 列表 |
| 3 | Skill 浏览 → 编辑 → 在线测试(SSE)| 选 skill → monaco 编辑 → SSE 流式响应 | axe 跑 Skill 测试页 |
| 4 | 对话 + SSE 长流 | 发问 → SSE 流 → 多轮 → 工具调用展开 | axe 跑 chat 主界面 |
| 5 | Multi-Agent 流可视化 | 触发 multi-agent → reactflow 渲染 → 节点点击 | — |

**Playwright spec 编写约定**:
- 用 `data-testid="..."` 选元素,**不**用 class / 样式选择器(class 改了测试就挂)
- baseURL 走 `process.env.PLAYWRIGHT_BASE_URL`(C Day 7 已配),local / staging / prod 三环境同源 spec
- 每个 spec 独立 storage state(登录态 fixture,见 `e2e/fixtures/auth.ts`)
- 截图 / 视频 only-on-failure(磁盘成本)
- **chromium / firefox / webkit 三浏览器都跑**(C playwright.config.ts 已配)

### 11.7 截图回归(Storybook Visual Regression)

**Phase 5 Day 49 接入**(等 chromium 决议):

| 工具 | 方案 |
|------|------|
| Chromatic(推荐)| Storybook 官方付费,免费版每月 5K 截图。PR 自动对比 baseline,有视觉 diff 标 fail |
| 自建 Playwright + pixelmatch | 免费但要写一堆胶水 |

**Day 49 与 C 协调**:
- Storybook stories 写到位(Day 11-12 + Phase 3)→ Chromatic 接入 PR workflow
- 双栈 Button / Input / Card 等基础组件双栈截图各自有 baseline
- token 改动(色 / 间距)→ Chromatic 标改动文件,reviewer 看 diff 决定是否合规

### 11.8 mock 策略

| 场景 | 工具 | 例子 |
|------|------|------|
| 单测 — 三方库 | `vi.mock()` | `vi.mock('axios')` |
| 集成测 — API | **msw**(优先)| `msw` handler in `setupTests.ts` |
| e2e — API | Playwright route mock(只在测错误态时用,正常走真后端 against staging)| `page.route('/api/v1/x', route => route.fulfill({...}))` |
| 生产 storybook | msw + 真 token JSON | story 内 `parameters.msw.handlers` |

**铁律:不用 `jest.mock` / `vi.mock` mock 业务 API**(改字段就疼) — 用 msw,改后端 schema 一处改完整链路同步。

### 11.9 coverage 工具 + 目标

```jsonc
// admin / app vitest.config.ts
{
  test: {
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      thresholds: {
        statements: 80,
        branches: 75,
        functions: 80,
        lines: 80,
      },
      exclude: [
        'src/api/generated/**',  // codegen 不算覆盖
        'src/main.ts(x)',
        '**/*.stories.ts(x)',
      ],
    },
  },
}
```

CI 覆盖率不达标 → fail PR(Phase 5 Day 49 由 C 启用 threshold)。

### 11.10 测试自检 checklist(写新功能前问自己)

- [ ] 我有纯函数 / utility 吗?写单测
- [ ] 我有 store action 吗?写单测
- [ ] 我有 composable / hook 吗?写单测
- [ ] 我接了新 API 吗?写契约测试(Day 24+)
- [ ] 我加了新页面吗?写一条 Playwright spec(P3 5 个核心流之外的 nice-to-have)
- [ ] 我加了新基础组件吗?写 Storybook story
- [ ] 我覆盖了错误态吗?(loading / empty / error 三态测试齐全)
- [ ] 我跑了 a11y 自查吗?(§10.9 checklist)

---

## 12. 性能 / 打包

> **目标**:Lighthouse 90+(Performance / Accessibility / Best Practices / SEO 四项),Web Vitals 绿区。Phase 5 Day 50 由 Agent C 接入 Lighthouse CI 卡门槛。

### 12.1 Web Vitals 4 指标(2024 起 INP 取代 FID)

| 指标 | 含义 | 绿区目标 |
|------|------|---------|
| **LCP** Largest Contentful Paint | 最大内容绘制 | ≤ 2.5s |
| **INP** Interaction to Next Paint | 交互到下次渲染(2024+ 取代 FID)| ≤ 200ms |
| **CLS** Cumulative Layout Shift | 累计布局偏移 | ≤ 0.1 |
| **FCP** First Contentful Paint(辅助)| 首次内容绘制 | ≤ 1.8s |
| **TTFB** Time to First Byte(辅助)| 首字节时间 | ≤ 0.8s |

**生产监控**:每次 `web-vitals` package 上报 → Cloudflare Worker → 自家时序数据库(Phase 4 Day 42 接入,与 OpenTelemetry / Langfuse 同口径)。

```ts
// admin/app main.ts 入口
import { onLCP, onINP, onCLS, onFCP, onTTFB } from 'web-vitals';
[onLCP, onINP, onCLS, onFCP, onTTFB].forEach((fn) => fn(reportToBackend));
```

### 12.2 bundle 大小预算

| 应用 | 总包 (gzip) | 主路由首屏 (gzip) | 单个 chunk 上限 |
|------|------------|------------------|----------------|
| **agentcook-admin** | ≤ 600 KB | ≤ 250 KB | ≤ 200 KB |
| **agentcook-app**(web) | ≤ 500 KB | ≤ 200 KB | ≤ 150 KB |
| **agentcook-app**(electron) | ≤ 1 MB(打包后)| n/a | n/a |

**测量工具**:
- `vite-bundle-visualizer` / `rollup-plugin-visualizer` — 本地 `pnpm build:analyze` 看 treemap
- `size-limit`(Phase 5 接入)— CI 卡 PR 是否超预算

### 12.3 vite 分包策略

**默认依赖大库(echarts / monaco / reactflow / mermaid)单独 chunk**:

```ts
// admin/vite.config.ts(app 同理,deps 名换)
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        'vue-core': ['vue', 'vue-router', 'pinia'],
        'element-plus': ['element-plus'],
        'echarts': ['echarts'],
        'monaco': ['monaco-editor'],
        // i18n 单独(语言包按需 lazy)
        'i18n': ['vue-i18n'],
      },
    },
  },
  chunkSizeWarningLimit: 200,  // 200KB 预算红线,超就警告
}
```

### 12.4 路由级 lazy + Suspense boundary

```ts
// admin Vue Router(已在 §5.2 写过)— 全部 dynamic import
{ path: '/plugins', component: () => import('@/views/plugin/PluginList.vue') }
```

```tsx
// app React 19 — Suspense + lazy
import { lazy, Suspense } from 'react';
const PluginList = lazy(() => import('@/pages/plugins'));

<Suspense fallback={<Skeleton.PluginList />}>
  <PluginList />
</Suspense>
```

**Suspense fallback 必须配 skeleton**(不是空白 / spinner) — 减少 CLS(`<Skeleton>` 占位与真实内容尺寸一致)。

### 12.5 React 19 性能特性(app 用上)

- **`use()` hook** — Promise / Context 同步消费,减少嵌套 Suspense
- **form actions + `useActionState`** — 表单提交无需手写 `useState + onSubmit + setLoading`
- **`useOptimistic`** — 乐观更新,网络慢时用户体验飞起(发消息立刻在 UI 显示,服务端确认前先乐观渲染)
- **不必显式 `useMemo` / `useCallback` 大部分场景**(React Compiler 2026 起稳定,自动 memo)— 仍需手动 memo 的场景:大对象 deps / context value

### 12.6 字体加载策略

```css
/* 自托管字体优先(不依赖 CDN)*/
@font-face {
  font-family: 'Inter';
  src: url('/fonts/Inter-var.woff2') format('woff2-variations');
  font-display: swap;       /* 关键:fallback 字体先显,再 swap,避免 FOIT */
  font-weight: 100 900;     /* variable font 一份覆盖所有 weight */
}

/* preload 关键字体 */
<link rel="preload" href="/fonts/Inter-var.woff2" as="font" type="font/woff2" crossorigin>
```

**中文字体(Day 14-15 P0-3 加入后)**:不自托管(动辄 5MB+),靠系统 fallback(PingFang SC / Microsoft YaHei),`font-display: swap` 防 FOIT。

### 12.7 图片优化

- **格式优先级**:AVIF > WebP > PNG/JPG;`<picture>` 多 source 自动 negotiate
- **响应式 sizes**:`<img srcset="x1.webp 1x, x2.webp 2x" sizes="...">`
- **lazy load**:`<img loading="lazy">` 默认开(首屏 hero 例外用 `loading="eager"`)
- **占位**:LQIP(low-quality image placeholder)/ blur-up,防 CLS
- **CDN 转换**:Cloudflare Images(Phase 4 Day 45 接入)— 自动 AVIF + 响应式 + 边缘 cache

### 12.8 React / Vue 防卡顿模式

| 场景 | 方法 |
|------|------|
| 大列表(plugin / skill / 历史会话 100+ 条)| `@tanstack/virtual`(双栈通用) |
| 复杂 chat 渲染(markdown + code + mermaid)| 单条消息 `React.memo` / Vue `defineComponent` + props 浅比对 |
| SSE 流式高频更新 | `useDeferredValue`(React 19)/ `requestAnimationFrame` 节流 batched setState |
| reactflow / dagre 节点多 | 禁用 `nodesDraggable`(用户用不到)+ `onlyRenderVisibleElements` |

### 12.9 Lighthouse CI(Phase 5 Day 50 由 C 接入)

```yaml
# .github/workflows/lighthouse.yml(C 写)
- name: Lighthouse CI
  uses: treosh/lighthouse-ci-action@v11
  with:
    urls: |
      https://staging.agentcook.cc/
      https://staging.agentcook.cc/plugins
      https://staging.agentcook.cc/chat
    budgetPath: ./.lighthouserc.json
    uploadArtifacts: true
```

`budget`:LCP ≤ 2.5s / INP ≤ 200ms / CLS ≤ 0.1 / Performance ≥ 90 / a11y ≥ 95。超阈值 fail PR(merge 主干前必过)。

### 12.10 性能自检 checklist

- [ ] 页面打开 LCP ≤ 2.5s 吗?(本地 throttle 4G + CPU 4x slowdown 复测)
- [ ] 主路由首屏包 ≤ 200-250KB(gzip)?
- [ ] 大依赖(echarts / monaco)有单独 chunk + 按需 lazy?
- [ ] 长列表 100+ 行有虚拟滚动?
- [ ] 图片有 width / height 防 CLS?有 lazy?
- [ ] 字体有 `font-display: swap`?
- [ ] React 19 表单 / 乐观更新场景用上 `useActionState` / `useOptimistic`?
- [ ] Suspense fallback 是 skeleton 不是 spinner?

---

## 13. 双栈一致性自检 checklist

每写完一个跨双栈的功能(plugin 列表 / chat 消息流 / 用户菜单等),回答以下问题:

- [ ] admin 和 app 显示的同一字段名一致吗?(eg. 都叫 "插件" 不混 "扩展")
- [ ] 错误文案是否走同一份 i18n key?(`error.network.timeout` 而不是各自硬编码)
- [ ] 同一颜色在 admin / app 像素值一致吗?(Storybook 双栈 Button 并排测试)
- [ ] 同一交互态(loading / empty / error)在 admin / app 有等价 UI 吗?
- [ ] API 类型是否从同一份 generated 来,无手写 duplication?
- [ ] 业务术语是否在 glossary.md 已登记?
- [ ] **快捷键双栈一致**(Cmd/Ctrl+S 双栈都是保存;Esc 双栈都关弹窗;Cmd/Ctrl+Enter 双栈都提交对话)
- [ ] **focus 顺序双栈一致**(键盘 Tab 走表单 / 列表 / 操作区的顺序在 admin / app 等价)

---

## 14. 决策点 — 已拍板(Day 9 晚 / Day 10 早)

| # | 项 | 拍板 | 落地章节 |
|---|----|------|---------|
| 1 | token 鉴权 | ✅ JWT 双 token:access 内存 15min + refresh httpOnly cookie 7d + CSRF double-submit | §7.3 |
| 2 | i18n 默认语言 | ✅ zh-CN 默认 + en-US 兜底,navigator.language 自动 + zustand persist | §8.4 |
| 3 | admin 路由模式 | ✅ history(Cloudflare Pages `_redirects` SPA fallback) | §5.1 |
| 4 | React 版本 | ✅ React 19 GA(简历加分,生态全适配) | §4.2 / §6.2 |
| 5 | 状态持久化 | ✅ 白名单:`ui` / `auth` / `chat` 三 store(pinia-plugin-persistedstate / zustand persist),TanStack Query 不 persist | §6.1 / §6.2 |
| 6 | API codegen | ✅ orval 双栈通吃 | §7.1 / §7.2 |

### 由 audit 衍生 / Day 10 内联落地的修订

| # | 项 | 落地 |
|---|----|------|
| 7 | `@tokens` 路径别名 → `@design-tokens/*` | ✅ §3.3 已修 |
| 8 | 错误码 enum Day 22 末必须冻结 | ✅ §7.2 / §8.8 已写 |
| 9 | i18n 路由策略(默认不带 lang URL,landing 页例外) | ✅ §8.5 已写 |
| 10 | SSE 401 流程(不走 axios 拦截器,手动 refresh + 重试一次) | ✅ §7.5 已写 |
| 11 | 后端 6 条接口约束(给 A Day 24 验收对照) | ✅ §7.6 已写 |

### Day 11 内联修订进度

| # | 项 | 状态 |
|---|----|------|
| 12 | Vue SFC 500 / TSX 300 行数差异化 | ✅ Day 11 §4.3 已修(F-9)|
| 13 | 路由守卫 401/403/404/5xx 全覆盖 | ⏳ Day 12 §5 续(F-11)|
| 14 | store 命名三类前缀 | ✅ Day 11 §6.4 已修(F-12)|
| 15 | SD adapter 警告框 | ✅ Day 11 §9 头部已加(F-13)|
| 16 | layouts/ 目录 + generouted 取舍 | ✅ Day 11 §4.1/§4.2 已修(F-7/F-8)|
| 17 | glossary.md 时机 | ✅ Day 10 §1.2 / §8.8 已写明 Phase 2 Day 22 加(F-17)|

### Day 12 v1.0 收官 audit 修订

| # | 项 | 状态 |
|---|----|------|
| 18 | ESLint flat config 完整版(extends + parserOptions + 30+ rules + Vue/React overrides + test/codegen ignores)| ✅ Day 12 §2.2 已修(F-4)|
| 19 | commit scope 9 个(core/providers/storage/admin/app/design-tokens/java/infra/docs)+ angular convention + commitlint CI | ✅ Day 12 §2.4 已修(F-5)|
| 20 | `tsconfig.base.json` 完整 dump(monorepo 三层结构 + verbatimModuleSyntax + exactOptionalPropertyTypes 等关键选项 + 不开就会怎样)| ✅ Day 12 §3.1 已修(F-6)|
| 21 | 路由守卫 4xx/5xx 全覆盖(401/403/404/5xx + redirect 保留 + Cloudflare/nginx fallback + layout 选择)| ✅ Day 12 §5.4 已修(F-11)|
| 22 | simple-git-hooks 完整(monorepo lint-staged scope + commit-msg + Python/Java 跨 Agent 集成 + --no-verify 应急)| ✅ Day 12 §2.3 已修(F-14)|

### Day 12 ADR-013 §7 增补

| # | 项 | 状态 |
|---|----|------|
| 23 | §7.7 双 API base + Java endpoint(路由分配 / 同源 vs 跨源部署 / vite proxy / orval 双源 4 entry / JWT 跨栈鉴权 JWKS / 错误码统一 / OTel trace 跨栈)| ✅ Day 12 已写;Day 24 末 D 出 java OpenAPI 后激活真 codegen |

---

## 历史

- **v1 草稿**(Day 8):写主体 §1-§6 + §9 + §13 主体,§7/§8/§10/§11/§12 仅占位
- **Day 9 audit**:`_internal/audit/frontend-conventions-self-review.md` 17 条 finding;`_internal/audit/frontend-decisions-pending.md` 6 + 5 决策细化
- **v1 续 Day 10**:§7 API client(orval + 双 token + SSE)+ §8 i18n(i18next + 自动检测 + persist + 路由策略)写完;§3.3 `@tokens` bug 修;§14 决策表 6 项 ✅ 已拍板 + 5 项 audit 内联落地
- **v1 续 Day 11**:§10 a11y(WCAG 2.1 AA + Radix + Element Plus + 键盘导航 + screen reader + prefers-* + axe-core)+ §11 测试(4 层金字塔 + vitest + msw + Pact + Playwright + Chromatic)+ §12 性能(Web Vitals + bundle 预算 + vite 分包 + lazy + 字体 / 图片 / Lighthouse CI)写完;audit F-7/F-8/F-9/F-12/F-13/F-15/F-16 共 7 条内联修订
- **v1.0 完整 ✅ Day 12 收官**:F-4 ESLint flat config 30+ 规则 + double stack overrides / F-5 commit angular convention + 9 scope + commitlint / F-6 tsconfig.base 完整 dump 三层 / F-11 路由守卫 4xx/5xx 全覆盖 / F-14 simple-git-hooks 完整(含 Python/Java 跨 Agent)5 条收尾;**§7.7 ADR-013 双 API base + Java endpoint** 增补(路由分配 / 双源 orval / JWKS 跨栈 JWT / 错误码统一 / OTel trace 跨栈)
- **v1.1**(Phase 3 落地后):根据真实写代码遇到的"规范走不通"反馈修订
