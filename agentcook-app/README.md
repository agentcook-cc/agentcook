# agentcook-app

> React 19 + Vite + Tailwind + shadcn/ui + Electron 双端用户端。流式 chat 真接 Qwen DashScope(Phase 4.6 ADR-017)+ 双语 i18n + Plugin Picker + 多媒体渲染(Mermaid / Markdown / 图片 / 文件)。

[![React](https://img.shields.io/badge/React-19-61dafb)]() [![Vite](https://img.shields.io/badge/Vite-5-646cff)]() [![TypeScript](https://img.shields.io/badge/TypeScript-5-3178c6)]() [![Electron](https://img.shields.io/badge/Electron-30-47848f)]() [![Tailwind](https://img.shields.io/badge/Tailwind-3-38bdf8)]()

---

## 包定位

`agentcook-app` 是 agentcook 平台的**终端用户产品**(end-user 直接用),服务对象:

- **个人用户**:Web 端访问 https://demo.agentcook.cc(Phase 4.5 P2 上线)+ 桌面 Electron 三平台(Mac / Windows / Linux,unsigned 版)
- **chat 场景**:流式 SSE 真接 Qwen → MarkdownRenderer 实时渲染 → 多 session 历史
- **Plugin / Skill 用户**:激活已发布 Plugin → chat 中调用 → SkillCallCard 展示工具调用 trace

**与 [agentcook-admin](../agentcook-admin/) 的边界**:admin 是平台管理面(运维 / Plugin 作者用),app 是终端用户面。两者**共享** design-tokens / API spec / 部分 SSE 解析逻辑,但**路由 / 视觉 / 状态独立**(详 ADR-009)。

---

## 6 路由(react-router-dom 6)

```text
/                    → Navigate /chat       (默认进 chat)
/login               → LoginPage            (placeholder-only inputs;P1 useEffect navigate /chat)
/chat                → ChatPage             (新会话,首次发言时自动 createSession)
/chat/:sessionId     → ChatPage             (历史会话 reload)
/500                 → ServerError fallback
*                    → NotFound2            (路由 fallback)
```

**SPA 守卫**:`isAuthenticated` 在 `LoginPage.tsx` `useEffect` 触发 `navigate('/chat', { replace: true })`(Day 51 e2e scenario 1 已验证)。`/chat` 内部 `if (!isAuthenticated) navigate('/login')`(防直 deep-link 绕过)。

---

## 10 业务组件

```text
ChatPage.tsx
├── SessionSidebar         — 会话历史 + 新建按钮
├── VirtualMessageList     — react-virtuoso 虚拟滚动,支持千条消息
│   └── MessageBubble      — 渲染分发器
│       ├── MarkdownRenderer  — react-markdown + remark-gfm + rehype-highlight
│       │   ├── MermaidBlock     — mermaid + DOMPurify svg sanitize(Day 51 接入)
│       │   ├── FileBlock        — 文件附件预览
│       │   └── ImageBlock       — 图片 lazy load
│       └── SkillCallCard     — Skill 工具调用 trace 卡片
├── ChatPluginPicker       — 激活已发布 Plugin
├── PluginSelector         — Plugin 列表 + filter
├── ChatInput              — 输入 + 发送按钮 + IME composition 处理
├── FileUploader           — 拖拽 + 多附件
└── ErrorBoundary          — 全局错误兜底
```

---

## 技术栈

| 类别 | 选型 | 理由 |
|---|---|---|
| 框架 | React 19.2 + TypeScript 5 | 最新 use API + Suspense + concurrent rendering |
| 构建 | Vite 5(`tsc --noEmit && vite build`) | dev HMR < 200ms;prod chunk gzip ~260 KB(主 entry) |
| 状态 | Zustand 4.5 | `auth.ts`(JWT)+ chat hooks 内部 useReducer |
| 路由 | react-router-dom 6.23 + `createBrowserRouter` | 类型安全 + nested route + lazy load |
| HTTP | axios 1.7 + interceptor | 与 [admin](../agentcook-admin/) 共享心智 |
| 数据请求 | `@tanstack/react-query` 5.28 | 缓存 + 后台 refetch + 错误恢复 |
| 流式 chat | 自研 `useSseChat` hook | EventSource + done frame parsing + retry |
| Markdown | react-markdown 9 + remark-gfm 4 + rehype-highlight 7 | 默认安全(无 rehype-raw,raw HTML 不渲染) |
| Mermaid | mermaid 11.15 + DOMPurify 3.4(svg profile) | securityLevel: 'strict' + 双层防护(Day 51) |
| 虚拟滚动 | react-virtuoso 4.7 | 千条消息丝滑滚动 |
| 桌面 | Electron 30 + electron-builder | 三平台 unsigned 包(canary / beta / stable) |
| i18n | i18next 23 + react-i18next 15 + `locales/{zh-CN,en-US}.json` | 双语就绪(Day 41-44) |
| Web Vitals | web-vitals 5.2 | 真用户 LCP/CLS/INP 上报(Day 50 baseline) |
| 安全 | DOMPurify 3.4(svg profile)+ react-markdown 默认 escape | XSS 输入消毒(Day 51 合规) |
| Design tokens | `@agentcook-cc/design-tokens`(workspace:*) | CSS variables,Tailwind preset 注入 |
| 测试 | vitest 1.x + JSDOM | 5 unit test |

---

## 5 min 快速上手

```bash
# 在 monorepo 根
pnpm install

# Web 模式
pnpm --filter @agentcook-cc/app dev
# → http://localhost:5174

# Electron 桌面模式(需先 build)
pnpm --filter @agentcook-cc/app electron:dev

# 后端依赖
make py-dev    # Python :8000(uvicorn agentcook_app.main:app)
make java-dev  # Java :8080(mvn spring-boot:run -pl agentcook-api)

# 默认登录
# 用户名:admin@agentcook.cc
# 密码:dev(Phase 3 dev 模式任意非空)
```

prod build + preview:
```bash
pnpm --filter @agentcook-cc/app build
pnpm --filter @agentcook-cc/app preview --port 4173
```

Electron 桌面包(三平台 unsigned):
```bash
pnpm --filter @agentcook-cc/app electron:build
# → release/{darwin,win32,linux}/agentcook-app-*.{dmg,exe,AppImage}
```

---

## 截图(Day 53 Agent B 落档)

| 视图 | 截图路径 |
|---|---|
| Login(placeholder-only inputs) | `docs/screenshots/app-01-login.png` |
| Chat(空会话,Plugin Picker 展开) | `docs/screenshots/app-02-chat-empty.png` |
| Chat(流式 qwen 回复 + Markdown 渲染) | `docs/screenshots/app-03-chat-streaming.png` |
| Chat(Mermaid 图表渲染 + DOMPurify 后) | `docs/screenshots/app-04-mermaid.png` |
| Chat(SkillCallCard 工具调用 trace) | `docs/screenshots/app-05-skill-trace.png` |

---

## chat 流式真栈数据流(Phase 4.6 ADR-017)

```text
用户输入 "你好"
  ↓
ChatInput.onSubmit
  ↓
useSseChat.send(text)
  ↓
POST http://localhost:5174/api/v1/chat/stream  # vite proxy 转发
  ↓ (proxy)
POST http://localhost:8000/api/v1/chat/stream
  ↓
agentcook_app.routers.chat:_stream_real_response (Phase 4.6)
  ↓
agentcook_providers.create_provider().stream_chat()  # default qwen-turbo
  ↓
DashScope OpenAI compat endpoint
  ↓ (SSE chunks)
ChatStreamFrame { content, done, metadata.{source,provider,output_chars,finish_reason} }
  ↓
useSseChat 解析 done=true 帧 → setState(message)
  ↓
MessageBubble → MarkdownRenderer → MermaidBlock(若有 mermaid code block,DOMPurify 后注入)
```

**fallback 链**(ADR-016 §3,Day 53-54 A 实现 zhipu 后扩):
```
qwen-turbo → glm-4-flash(zhipu)→ qwen-plus → echo
```

---

## 目录结构

```text
agentcook-app/
├── src/
│   ├── api/              # axios + openapi-typescript types(从 ../docs/api/ 自动生成)
│   ├── components/       # 10 业务组件 + media/(MermaidBlock/FileBlock/ImageBlock)+ __tests__
│   ├── hooks/            # useSseChat / useSession
│   ├── i18n/             # i18next 配置
│   ├── layouts/          # MainLayout(顶栏 + sidebar)
│   ├── locales/          # zh-CN.json + en-US.json
│   ├── observability/    # web-vitals 上报
│   ├── pages/            # ChatPage / LoginPage + error/
│   ├── stores/           # Zustand: auth.ts + __tests__/
│   ├── styles/           # 全局 CSS + Tailwind 入口
│   ├── test/             # vitest setup / mocks
│   ├── types/            # 业务类型(独立于 generated API types)
│   └── router.tsx        # createBrowserRouter 6 路由
├── electron/             # main.ts + preload.ts(Electron skeleton)
├── electron-builder.yml  # 三平台打包配置(unsigned)
├── tests/                # (空,vitest 在 src/__tests__/)
└── vite.config.ts        # vite proxy /api/* → :8000(Python)/ :8080(Java)
```

总 LOC ~5,000 行(`*.ts` + `*.tsx`)。

---

## API 客户端 — 双 spec 自动生成 types

与 [admin](../agentcook-admin/) 同款流程:

```bash
pnpm --filter @agentcook-cc/app gen:api          # 双 spec 一起
pnpm --filter @agentcook-cc/app gen:api:python   # 单生成 v1.yaml(Python)
pnpm --filter @agentcook-cc/app gen:api:java     # 单生成 java-v1.yaml(Java)
```

`src/api/client.ts` 统一 axios:JWT Bearer header + 401 拦截 → `Navigate('/login')`。

---

## 测试

```bash
pnpm --filter @agentcook-cc/app test       # 5 vitest
pnpm --filter @agentcook-cc/app lint       # eslint
pnpm --filter @agentcook-cc/app build      # tsc --noEmit + vite build
```

5 vitest:
- `stores/__tests__/auth.test.ts` — JWT 存取 / clear / Bearer header 拼接
- `components/__tests__/MessageBubble.test.tsx` — 渲染分发(text / markdown / skill trace)
- `components/__tests__/FileUploader.test.tsx` — 拖拽 + 多附件 + 大小校验
- `components/media/__tests__/FileBlock.test.tsx` — 文件预览
- `components/media/__tests__/ImageBlock.test.tsx` — 图片 lazy load

E2E(Playwright)在 monorepo 顶层 `e2e/app/`,5 场景 × 2 browser(Chromium + Firefox)= 10 PASS(Day 48-49)。

---

## 性能基线(Day 50-51 Lighthouse)

| Metric | Day 50 prod | Day 51 (DOMPurify 后) |
|---|---:|---:|
| Performance | 94 | 94 |
| Accessibility | 100 | 100 |
| Best Practices | 96 | 96 |
| SEO | 82 🟡 | 82(Phase 5 buffer 修) |
| LCP | 2.5s | 2.5s |
| CLS | 0 | 0 |
| TBT | 0ms | 0ms |
| `csp-xss` | 100 ✅ | 100 ✅ |

Web Vitals under load(详 [`webvitals-under-load.md`](../../agentcook/tutorial/_internal/audit/phase5-day50-lighthouse/webvitals-under-load.md)):
- TTFB +291% @ 500u(后端瓶颈传导)
- LCP +79% @ 500u
- CLS 始终 ~0(前端布局稳定 ✅)

bundle chunk(prod build):
- 主 entry gzip ~260 KB
- MermaidBlock chunk 619 KB(含 mermaid + DOMPurify)— Phase 5 buffer dynamic import 拆
- wardley chunk 615 KB — 同上

---

## 相关 ADR

- [ADR-003](../docs/adr/ADR-003-design-tokens-strategy.md) — design tokens 跨端策略
- [ADR-009](../docs/adr/ADR-009-parallel-frontend.md) — admin / app 并行前端拆分
- [ADR-010](../docs/adr/ADR-010-electron-unsigned-distribution.md) — Electron unsigned 三平台路线
- [ADR-016](../docs/adr/ADR-016-llm-provider-fallback-chain.md) — LLM provider fallback 链
- [ADR-017](../docs/adr/ADR-017-chat-real-qwen-integration.md) — chat 真接 Qwen 时机

---

## 安全(Day 51 合规自检)

| 维度 | 现状 |
|---|---|
| XSS 输入消毒 | DOMPurify svg profile + mermaid `securityLevel: 'strict'`(MermaidBlock,详 ADR/progress Day 51) |
| Markdown 渲染 | react-markdown 默认安全(无 `rehype-raw`,raw HTML 不渲染) |
| `dangerouslySetInnerHTML` | 全仓库 0 命中 |
| CSRF | 模型不适用(localStorage + Bearer header,不依赖 cookie;详 progress Day 51 §3) |
| JWT 存储 | localStorage(prod 时主威胁是 XSS,已 §1 加固) |
| `csp-xss` Lighthouse audit | 100 ✅ |

---

## 开发约定

- **不手写 API types**:`pnpm gen:api`,yaml 是单一真源
- **不直接 import design-tokens 内部文件**:用 `@agentcook-cc/design-tokens` 包入口
- **不写新 axios 实例**:统一 `src/api/client.ts`(JWT + 401 拦截)
- **不在 markdown 内嵌 raw HTML**:react-markdown 默认会 escape
- **mermaid code block 必经 DOMPurify**:`MermaidBlock` 已统一处理
- **新 SSE 流接入**:复用 `useSseChat` 模式(parsedFrame / done detection / cleanup)
- **新增 chat 组件**:必加到 `MessageBubble.tsx` 渲染分发表(防止 fallback 到 plain text)

---

## License

MIT — 同 monorepo
