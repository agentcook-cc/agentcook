# Legacy HTML Showcase(已退役)

> 这是 Phase 0(2026-05-16,助手 F 单 Agent 模式)交付的 design tokens 静态展示页。Phase 1 Day 7(2026-05-17)起由 Storybook 8 + html-vite 替代。

## 为什么退役

`index.html` 中所有色值 / 字号 / 间距 / 阴影**直接 inline 硬编码**(`background: #3b82f6;` 而不是 `var(--color-primary-500)`)。`tokens/*.json` 改了,这个页面不会跟着变,违背"single source of truth"原则。

## 替代方案

见上一级 `.storybook/` + `stories/`:Storybook 8 + `@storybook/html-vite` 双栈展示框架,所有 stories `import` `tokens/*.json`,token 改 → 故事自动同步。

启动:

```bash
pnpm install
pnpm --filter @agentcook-cc/design-tokens storybook
```

## 何时可删

Phase 1 Day 15 review 通过后,本目录可整体删除。当前保留作为 v0 历史快照,方便对比"硬编码双轨"vs"数据驱动单源"两种工程做法的差异(教程章节 22 admin 段可作为引子素材)。

## 不要做的事

- 不要在 `index.html` 上继续修 bug(改了也是徒劳,Storybook 是新信源)
- 不要往这里添新 token 展示(去 `stories/*.stories.ts`)
