# Playwright 本地回归

先在仓库根目录安装依赖并启动数据库与缓存：

```bash
uv sync --python 3.12 --all-packages --all-extras --group dev
pnpm install
pnpm --filter @agentcook-cc/design-tokens build
docker compose -f docker-compose.dev.yml up -d postgres-business redis
(cd agentcook-java && mvn -B -DskipTests package)
```

在不同终端启动业务后端和两个运行时：

```bash
java -jar agentcook-java/agentcook-api/target/agentcook-api-0.1.0-SNAPSHOT.jar --spring.profiles.active=dev
```

```bash
AGENTCOOK_AUTH_MODE=required AGENTCOOK_JWT_ISSUER=agentcook-java \
AGENTCOOK_JAVA_BASE_URL=http://127.0.0.1:8080 AGENTCOOK_QUOTA_ENABLED=true \
AGENTCOOK_QUOTA_PRIMARY_PROVIDER=mock AGENTCOOK_QUOTA_PRIMARY_MODEL='' \
AGENTCOOK_QUOTA_FALLBACK_PROVIDER=mock AGENTCOOK_QUOTA_FALLBACK_MODEL='' \
AGENTCOOK_MOCK_DELAY_MS=20 uv run uvicorn agentcook_app.main:app --port 8000
```

```bash
AGENTCOOK_AUTH_MODE=optional AGENTCOOK_MOCK_DELAY_MS=20 \
  uv run uvicorn agentcook_app.main:app --port 8001
```

在各自的终端启动三个 Vite 进程：

```bash
pnpm --filter @agentcook-cc/admin dev --port 5173
pnpm --filter @agentcook-cc/app dev --port 5174
AGENTCOOK_PY_API=http://127.0.0.1:8001 pnpm --filter @agentcook-cc/app dev --port 5175
```

在并行验收前先登录一次，以初始化本地数据库中的 `admin`。已有管理员账号时，用 `E2E_ADMIN_PASSWORD` 提供实际密码。

```bash
jq -nc --arg password "${E2E_ADMIN_PASSWORD:-admin-password-123}" \
  '{username:"admin", password:$password}' | \
  curl -fsS http://127.0.0.1:8080/api/v1/auth/login \
    -H 'Content-Type: application/json' --data-binary @- -o /dev/null

PLAYWRIGHT_BASE_URL=http://localhost:5173 pnpm e2e
```

`app` 测匿名对话与前端状态，`app-full-stack` 测真实注册、工具调用、额度扣减和会话恢复，`admin` 测控制台和角色限制。使用 `PLAYWRIGHT_BASE_URL_ANONYMOUS`、`PLAYWRIGHT_BASE_URL_APP` 和 `PLAYWRIGHT_BASE_URL_ADMIN` 可以指定对应站点。可通过 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 使用已安装的浏览器。Pact Broker 截图属于单独的审计场景，由 `PLAYWRIGHT_AUDIT=1` 启用。
