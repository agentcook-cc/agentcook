# ADR-003: Admin + App 共享 Design Tokens

## Status

Accepted (2026-05-16)

## Context

项目包含两套前端应用：
- **admin**：管理后台，使用 Vue3 + Element Plus
- **app**：用户前端，使用 Next.js + shadcn/ui（Tailwind CSS）

两套技术栈对应两套设计系统，导致视觉割裂：颜色色值不一致、间距规范不统一、圆角风格差异等问题，严重影响品牌一致性。

## Decision

建立独立仓库 `agentcook-design-tokens`，使用 **Style Dictionary** 作为 Token 编译引擎。

所有设计原子全部 token 化：
- 颜色（Color Palette）
- 字体（Typography）
- 间距（Spacing）
- 阴影（Shadows）
- 圆角（Border Radius）

接入方式：
- **admin（Element Plus）**：通过自定义 theme 文件注入 token，覆盖 Element Plus 默认变量
- **app（Tailwind CSS）**：在 `tailwind.config.js` 中引用编译后的 JSON token，扩展 Tailwind 主题

Token 源文件采用 W3C Design Tokens 格式（JSON），设计师可通过 Figma Tokens 插件同步设计稿与代码。

## Consequences

### Positive
- **双栈视觉一致**：admin 与 app 共享同一套设计语言，消除视觉割裂
- **设计师友好**：Figma tokens 可与代码双向同步，设计即代码

### Negative
- **额外维护成本**：多一个独立仓库需纳入 CI/CD 与版本管理
- **变更验证复杂**：token 修改需同时在 admin 和 app 两端回归测试，避免样式崩坏
