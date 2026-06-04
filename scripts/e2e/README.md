# scripts/e2e/ — Playwright headless 自动化脚本

部署闭环压测 / UI 回归 / 教程截图素材生成的 Playwright headless 脚本集。

## 现有脚本

| 脚本                       | 用途                                                                    | 出处                                                                      |
| -------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `admin-app-smoke-spec.mjs` | admin (:5173) + app (:5174) 9 截图自动化 + 真发 chat + 收 console.error | Day 70+ Agent B 部署闭环压测产出(原 `scripts/deployment-loop-b-spec.mjs`) |

## 怎么跑

### 前置

```bash
# 后端 + admin + app 全部起来
make dev                          # 后端 + 9 docker 服务
cd agentcook-admin && pnpm dev    # :5173
cd agentcook-app && pnpm dev      # :5174

# Playwright chromium 浏览器(首次)
npx playwright install chromium
```

### 跑

```bash
# 默认截图落 scripts/e2e/screenshots/(已 .gitignore)
node scripts/e2e/admin-app-smoke-spec.mjs

# 或自定义截图目录(压测产物放压测 _internal 目录下时用)
SCREENSHOTS_DIR=/path/to/your/dir node scripts/e2e/admin-app-smoke-spec.mjs
```

## 已知 limitation(Day 70+ 首发期)

按 [`DEPLOYMENT.md`](../../DEPLOYMENT.md) 顶部首发期 limitation 段:

- **chat 端到端**:必须先 `.env` 注入 Qwen key + `uv sync --all-packages --all-extras`,否则 chat SSE 走 mock(详 W3 ① A 修)
- **admin /users/me**:Day 70+ W3 ① D 修复后正常,修复前 admin login 死循环

## 演进

未来添加 e2e 脚本时:

- 命名 convention:`<scope>-<purpose>-spec.mjs`(e.g. `admin-plugin-crud-spec.mjs`)
- 截图统一落 `scripts/e2e/screenshots/`(已 .gitignore)
- 顶部 docstring 必含:用途 / 谁用 / 怎么跑 / 已知 limitation / 演进轨迹(模仿 `admin-app-smoke-spec.mjs`)
