# agentcook-admin

> Vue 3 + Element Plus + TypeScript 后台管理端。Plugin / Skill / Connector / User / Permission 五大资源 CRUD + Observability iframe + Log stream。

[![Vue](https://img.shields.io/badge/Vue-3.4-42b883)]() [![Element Plus](https://img.shields.io/badge/Element_Plus-2.7-409eff)]() [![TypeScript](https://img.shields.io/badge/TypeScript-5-3178c6)]() [![Vite](https://img.shields.io/badge/Vite-5-646cff)]() [![pnpm](https://img.shields.io/badge/pnpm-9-f69220)]()

---

## 包定位

`agentcook-admin` 是 agentcook 平台的**运维 / 开发 / 内容管理后台**,服务对象:

- **平台运维**:接入 K8s 监控、Langfuse cost trace、Prometheus 告警(Day 31 起 iframe 嵌入,详 ADR-005)
- **Skill / Plugin 作者**:CRUD 资源 + 在线测试 SkillTestDialog(SSE 调 `/api/v1/skills/{id}/test/stream`)
- **租户管理员**:User / Permission 配置 + 跨语言 JWT 颁发(Java :8080 → Python :8000 透明)

不是终端用户产品(终端用户用 [agentcook-app](../agentcook-app/))。

---

## 9 view × 8 路由总图

```text
/login                 → LoginView         (dev 模式任意密码,Phase 5 Day 56 切真验证)
/                      → 重定向 /dashboard
├── /dashboard         → DashboardView     (4 卡片 + 调用量趋势 + 实时 chat 数)
├── /plugins           → PluginListView    (Plugin CRUD + ajv schema 校验)
├── /skills            → SkillListView     (Skill 元数据 + 在线 SkillTestDialog SSE)
├── /connectors        → ConnectorListView (DingTalk / Feishu / Lark Bot 配置)
├── /users             → UserListView      (User CRUD + 搜索 + 分页)
├── /permissions       → PermissionGroupView (RBAC 矩阵编辑器)
├── /observability     → ObservabilityView (Jaeger / Grafana / Langfuse iframe)
└── /logs              → LogStreamView     (实时 SSE log tail + 过滤)
```

错误页:`/401 Unauthorized` / `/403 Forbidden` / `/500 ServerError` / 404 fallback。

---

## 技术栈

| 类别 | 选型 | 理由 |
|---|---|---|
| 框架 | Vue 3.4 + Composition API | 与 Element Plus 生态契合;mall-admin-web 同款心智 |
| UI | Element Plus 2.7 + `@element-plus/icons-vue` | 后台密集 form / table 优势 |
| 状态 | Pinia 2.1 | `auth.ts`(JWT)+ `theme.ts`(明暗主题) |
| 路由 | Vue Router 4.3 + `beforeEach` 守卫 | 路由级权限 + redirect 历史 |
| HTTP | axios 1.7 + interceptor 注入 `Authorization: Bearer` | 同 [agentcook-app](../agentcook-app/) 共享心智 |
| 表单校验 | ajv 8.17(JSON Schema) | Plugin schema 与后端 Pydantic 同源 |
| 图表 | echarts 5.5 + vue-echarts 7 | dashboard 趋势 |
| 编辑器 | monaco-editor 0.45 + `@guolao/vue-monaco-editor` | Plugin schema 在线编辑 |
| i18n | vue-i18n 9.14 + `locales/{zh-CN,en-US}.json` | 双语就绪(Day 41-44 落地) |
| Web Vitals | web-vitals 5.2 | 真用户 LCP/CLS/INP 上报(Day 50 baseline) |
| Design tokens | `@agentcook-cc/design-tokens`(workspace:*) | CSS variables + Element Plus theme override |
| Build | Vite 5 + `vue-tsc --noEmit` | dev HMR < 200ms;prod gzip < 500KB |
| 测试 | vitest 1.x + JSDOM | 7 unit test(详 §测试) |

---

## 5 min 快速上手

```bash
# 在 monorepo 根
pnpm install

# 起 admin dev server
pnpm --filter @agentcook-cc/admin dev
# → http://localhost:5173

# 后端依赖(任一终端启动,admin 通过 vite proxy 自动转发)
make py-dev    # Python :8000(uvicorn agentcook_app.main:app)
make java-dev  # Java :8080(mvn spring-boot:run -pl agentcook-api)

# 默认登录:dev 模式任意非空密码
# 用户名:admin@agentcook.cc
# 密码:dev
```

prod build + preview:
```bash
pnpm --filter @agentcook-cc/admin build
pnpm --filter @agentcook-cc/admin preview --port 4172
```

---

## 截图

> 全部 prod build 真访问(`vite build` + `vite preview`)。Day 52 Agent B 落档,源 `docs/screenshots/admin-*.png`。

| 视图 | 截图路径 |
|---|---|
| Login(dev 模式) | `docs/screenshots/admin-01-login.png` |
| Dashboard(4 卡片 + 趋势) | `docs/screenshots/admin-02-dashboard.png` |
| Plugin List(CRUD + ajv schema) | `docs/screenshots/admin-03-plugins.png` |

---

## 目录结构

```text
agentcook-admin/
├── src/
│   ├── api/              # axios + openapi-typescript 自动生成的 types
│   │   ├── client.ts     # axios instance + JWT interceptor
│   │   ├── types.python.gen.ts  # gen:api:python 产出(从 ../docs/api/v1.yaml)
│   │   └── types.java.gen.ts    # gen:api:java   产出(从 ../docs/api/java-v1.yaml)
│   ├── components/       # 通用 UI(脱离业务的)
│   ├── composables/      # 复用逻辑(useTable / useDialog / useSseStream)
│   ├── config/menu.ts    # 侧栏菜单单一真源
│   ├── i18n/             # vue-i18n 配置
│   ├── layouts/          # MainLayout(侧栏 + 面包屑)
│   ├── locales/          # zh-CN.json + en-US.json
│   ├── observability/    # web-vitals 上报 + iframe 安全策略
│   ├── router/index.ts   # 8 路由 + auth 守卫
│   ├── stores/           # Pinia: auth.ts + theme.ts
│   ├── views/            # 9 view(8 路由 + 1 Permission 编辑)
│   │   ├── connectors/   # DingTalk / Feishu / Lark 子表单
│   │   ├── plugins/      # PluginEditor.vue + PluginTestDialog.vue
│   │   ├── skills/       # SkillEditor.vue + SkillTestDialog.vue(SSE)
│   │   └── users/        # UserEditor.vue + UserDeleteDialog.vue
│   └── main.ts           # createApp + 全局 ajv + Element Plus
├── tests/                # 7 vitest unit test
└── vite.config.ts        # vite proxy /api/* → :8000(Python)/ :8080(Java)
```

总 LOC ~7,500 行(`*.ts` + `*.vue`)。

---

## API 客户端 — 双 spec 自动生成 types

后端是 Python(:8000)+ Java(:8080)双 spec(详 [docs/api/](../docs/api/))。admin 用 openapi-typescript 从 yaml 生成 TS 类型,**禁止手写 API types**:

```bash
# 拉最新 yaml 重生成
pnpm --filter @agentcook-cc/admin gen:api

# 单独生成
pnpm --filter @agentcook-cc/admin gen:api:python
pnpm --filter @agentcook-cc/admin gen:api:java
```

axios client 在 `src/api/client.ts`:
- 请求拦截器:从 `useAuthStore().accessToken` 注入 `Authorization: Bearer <jwt>`
- 响应拦截器:401 → router push `/login`(refresh token 流程在 Phase 5 末加)

---

## 测试

```bash
pnpm --filter @agentcook-cc/admin test       # 7 vitest
pnpm --filter @agentcook-cc/admin lint       # eslint
pnpm --filter @agentcook-cc/admin build      # vue-tsc --noEmit + vite build
```

7 unit test(`tests/`):
- `auth-store.test.ts` — JWT 存取 / 过期 / clear
- `plugin-schema.test.ts` — ajv 校验边界
- `smoke.test.ts` — 主页 mount 不崩
- `connector-mapper.test.ts` — 后端 schema → 前端 form mapper
- `log-parser.test.ts` — SSE log 帧解析
- `sse-parse.test.ts` — SSE 通用解析器(共享 [agentcook-app](../agentcook-app/))
- `permission-matrix.test.ts` — RBAC 矩阵编辑

E2E(Playwright)在 monorepo 顶层 `e2e/admin/`(详 monorepo README)。

---

## 性能基线(Day 50 webvitals + Day 51 Lighthouse)

| Metric | Day 50 | Day 51(after DOMPurify) |
|---|---:|---:|
| Lighthouse Performance | 94 | 94 |
| Lighthouse Accessibility | 100 | 100 |
| Lighthouse Best Practices | 96 | 96 |
| Lighthouse SEO | 82 🟡 | 82(Phase 5 buffer 修 meta-description + robots.txt) |
| LCP | 2.5s | 2.5s |
| CLS | 0 | 0 |
| TBT | 0ms | 0ms |

Web Vitals under load 退化曲线见 [`tutorial/_internal/audit/phase5-day50-lighthouse/webvitals-under-load.md`](../../agentcook/tutorial/_internal/audit/phase5-day50-lighthouse/webvitals-under-load.md)(TTFB +291% @ 500u,LCP +79% @ 500u)。

---

## 相关 ADR

- [ADR-003](../docs/adr/ADR-003-design-tokens-strategy.md) — design tokens 跨端策略
- [ADR-005](../docs/adr/ADR-005-observability-stack.md) — Observability iframe 嵌入策略
- [ADR-009](../docs/adr/ADR-009-parallel-frontend.md) — admin / app 并行前端拆分
- [ADR-013](../docs/adr/ADR-013-java-backend-for-frontend.md) — Java BFF + Python 双后端

---

## 开发约定

- **不手写 API types**:用 `pnpm gen:api` 从 yaml 生成(yaml 是单一真源)
- **不直接 import design-tokens 内部文件**:用 `@agentcook-cc/design-tokens` 包入口(详 [agentcook-design-tokens README](../agentcook-design-tokens/README.md))
- **不写新 axios 实例**:统一用 `src/api/client.ts`(JWT 注入 + 401 拦截已统一)
- **路由级权限**:在 `router/index.ts` `beforeEach` 守卫,不在 view 内做(防漏)
- **SSE 流式**:复用 `composables/useSseStream`(parsedFrame / connection state / cleanup)

---

## License

MIT — 同 monorepo
