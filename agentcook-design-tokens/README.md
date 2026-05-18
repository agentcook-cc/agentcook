# agentcook-design-tokens

> 共享设计系统 — admin (Vue 3 + Element Plus) 与 app (React + Tailwind + shadcn/ui) 双栈视觉一致性的单一信源。

## 目录

```
agentcook-design-tokens/
├── tokens/                    ← 6 类 token JSON(单一信源)
│   ├── color.json
│   ├── typography.json
│   ├── spacing.json
│   ├── radius.json
│   ├── shadow.json
│   └── motion.json
├── style-dictionary.config.js ← 4 端编译配置(css / element-plus / tailwind / figma)
├── .storybook/                ← Storybook 8 + html-vite 配置
├── stories/                   ← 6 类 token 故事(数据驱动展示)
├── legacy-html-showcase/      ← Phase 0 旧版静态展示(已退役,见目录内 README)
└── dist/                      ← Style Dictionary 编译产物(运行 `pnpm build` 生成)
```

## 使用

### 在 admin / app 内消费

```ts
// admin (Vue 3) 或 app (React) 的入口
import '@agentcook-cc/design-tokens/dist/css/variables.css';

// 或在 Tailwind preset 里
import preset from '@agentcook-cc/design-tokens/dist/tailwind/preset.js';
```

### 修改 token

只改 `tokens/*.json` → 跑 `pnpm build` → 4 端产物自动同步。

### 浏览所有 token + 组件示例

```bash
# monorepo 根目录
pnpm install

# 启 Storybook(端口 6006)
pnpm --filter @agentcook-cc/design-tokens storybook

# 编译 token 到 4 端产物
pnpm --filter @agentcook-cc/design-tokens build

# 类型检查
pnpm --filter @agentcook-cc/design-tokens typecheck
```

## 当前阶段(Phase 1 Day 7,2026-05-17)

- ✅ 6 类 token JSON 骨架就位
- ✅ Style Dictionary 4 端编译配置(CSS variables 直接可用;Element Plus / Tailwind / Figma 三端 adapter Day 14-15 完善)
- ✅ Storybook 8 + html-vite 框架就绪
- ✅ 6 类 token 数据驱动 stories 初版(`Foundation/*`)
- 🚧 token 缺补清单 — 见 `tutorial/_internal/progress/agent-b-day-6-tokens-review.md`,Day 14-15 / Phase 2 Day 22-23 分批补
- 🚧 Vue / React 双栈组件 stories(Day 8 加 Element Plus Button + shadcn/ui Button 并排展示)

## 双栈策略

Storybook 8 单实例配置为 `@storybook/html-vite` framework,token 故事用纯 HTML 渲染(从 JSON 读)。Day 8 起 Vue / React 组件 stories 以 `render()` 函数手动 mount(`createApp` / `createRoot`),实现一站展示双栈 — 不拆 storybook-vue / storybook-react 双实例,降低维护成本。

## 设计原则

1. **Atomic → Semantic → Component 三层** — 当前 atomic 完整,Phase 1 末补 semantic(`text.primary` / `bg.surface` / `border.subtle`)
2. **单一信源** — token 改动只发生在 `tokens/*.json`,展示与消费方都从此处派生
3. **dark mode 是 token concern** — Phase 2 Day 22-23 引入 dark token 集 + Storybook 主题切换
4. **双栈零认知差** — admin / app 同一 token 出同一像素值

## 参考

- ADR-003(`tutorial/_internal/L3-strategy/v6-architecture-rationale.md`)
- 接手 review:`tutorial/_internal/progress/agent-b-day-6-tokens-review.md`
- docs 工具决策:`tutorial/_internal/progress/agent-b-day-6-docs-tooling-decision.md`
