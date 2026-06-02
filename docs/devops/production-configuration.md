# 生产配置完整清单(agentcook prod)

> **目标读者**:DevOps / SRE / 后端 lead。本文档列出 demo.agentcook.cc 真生产环境的完整配置 — env vars / secrets / resource limits / replicas / probes / HPA / PDB / NetworkPolicy / PrometheusRule + 与 staging 的差异 + 启动顺序 + 健康检查 + Blue-Green 切流量步骤。
>
> **配套**:
>
> - `k8s-operations-manual.md`(运维操作)
> - `troubleshooting-runbook.md`(故障排查)
> - `monitoring-alerts-sop.md`(告警 SOP)
> - ADR-005(Observability)· ADR-006(Blue-Green)· ADR-016(provider fallback)
> - Day 50 perf report(C / A 调优)· Day 51 D Tomcat/HikariCP commit

---

## 1. 配置文件分工

| 文件                                             | 作用                                         | 维护方        |
| ------------------------------------------------ | -------------------------------------------- | ------------- |
| `deploy/helm/agentcook/values.yaml`              | base / dev 默认                              | A 起 / C 维护 |
| `deploy/helm/agentcook/values-staging.yaml`      | staging.agentcook.cc override                | C             |
| `deploy/helm/agentcook/values-prod.yaml`         | demo.agentcook.cc override                   | C             |
| `deploy/helm/agentcook/templates/configmap.yaml` | 应用配置 ConfigMap                           | C             |
| `deploy/helm/agentcook/templates/secret.yaml`    | dev 占位 Secret(prod 用 ExternalSecret 替换) | C / 安全审核  |

**单一来源原则**:`values.yaml` 是基线,`values-prod.yaml` 只放真正与 base 不同的 override(replicas / resources / sampler / domain / TLS / extraArgs / env)。

---

## 2. 5 服务 prod 配置全表

| 服务           |           replicas | requests(mem/cpu) | limits(mem/cpu)                 | extraArgs / env tuning                                                                                                                                                            | 端口                  |
| -------------- | -----------------: | ----------------- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------- |
| `agent-core`   | 2(HPA min=1 max=5) | 256Mi / 250m      | 512Mi / 500m                    | `args: ["--workers", "4"]`(Day 50 C / -47% login p95)                                                                                                                             | 8000 HTTP             |
| `admin-bff`    | 2(HPA min=1 max=5) | 512Mi / 250m      | **1Gi**(D Day 50 ea0c5cb)/ 500m | env: `SERVER_TOMCAT_THREADS_MAX=400` `SERVER_TOMCAT_ACCEPT_COUNT=200` `SPRING_DATASOURCE_HIKARI_MAXIMUM_POOL_SIZE=30` `SPRING_DATASOURCE_HIKARI_MINIMUM_IDLE=5`(D Day 51 7f320c4) | 8080 HTTP / 9090 gRPC |
| `connector`    |                  1 | 256Mi / 250m      | 512Mi / 500m                    | (默认)                                                                                                                                                                            | 8082 HTTP             |
| `admin-static` |                  1 | 128Mi / 100m      | 256Mi / 200m                    | (nginx 默认)                                                                                                                                                                      | 80 HTTP               |
| `app-static`   |                  1 | 128Mi / 100m      | 256Mi / 200m                    | (nginx 默认)                                                                                                                                                                      | 80 HTTP               |

**JVM 参数(admin-bff,Java 端 Day 50 D ea0c5cb)**:`-Xmx768m -XX:+AlwaysPreTouch -XX:+UseG1GC -Xlog:gc*:stdout:time`,在 image Dockerfile `JAVA_TOOL_OPTIONS` 落,1Gi limit 留 ~256Mi 给 metaspace + 直接内存。

---

## 3. ConfigMap / Secret 完整 key

### 3.1 ConfigMap(明文配置)

| Key            | 用途          | prod 值                                              |
| -------------- | ------------- | ---------------------------------------------------- |
| `DATABASE_URL` | postgres 连接 | `postgresql://postgres@postgres-prod:5432/agentcook` |
| `REDIS_URL`    | redis 连接    | `redis://redis-prod:6379/0`                          |
| `ETCD_URL`     | etcd 服务发现 | `etcd://etcd-server:2379`                            |
| `LOG_LEVEL`    | log 级别      | `info`(prod)/ `debug`(staging)                       |

### 3.2 Secret(密文 — ExternalSecret 推荐 / SealedSecret 备选)

| Key                                           | 用途                                               | 来源                                                        |
| --------------------------------------------- | -------------------------------------------------- | ----------------------------------------------------------- |
| `DB_PASSWORD`                                 | postgres 密码                                      | Vault / AWS SM / 1Password                                  |
| `JWT_SECRET`                                  | HS256 签名密钥(长期方案 RS256+JWKS 见 D Day 51 §4) | ExternalSecret                                              |
| `QWEN_API_KEY`                                | 阿里 Qwen API key                                  | ExternalSecret                                              |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Langfuse trace 上报                                | ExternalSecret                                              |
| `OAUTH_*_CLIENT_SECRET`                       | OAuth 各 provider                                  | ExternalSecret(D Day 51 OAuth state Phase 4 Day 33-34 落地) |

**安全决策树**(详 `k8s-operations-manual.md` §5.1):

- prod 必须用 ExternalSecret(Vault / AWS SM)或 SealedSecret(密文 commit 进 git)
- 不接受 `--set secret.dbPassword=...` 命令行注入(留 shell history)
- 不接受 `dev-only-do-not-use-in-prod` fallback(security.py 自动 fail-fast,Day 52 A Y1 落地后)

---

## 4. 健康检查配置

| 服务       | livenessProbe                                                              | readinessProbe                                                                      | startupProbe                                                               |
| ---------- | -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| agent-core | GET `/health` :8000 / delay 30s / period 10s                               | GET `/health` :8000 / delay 5s / period 5s                                          | (无,Python 启动快)                                                         |
| admin-bff  | GET `/actuator/health` :8080 / delay 60s / period 15s / failureThreshold 3 | GET `/actuator/health/readiness` :8080 / delay 15s / period 5s / failureThreshold 3 | GET `/actuator/health` :8080 / failureThreshold 30 / period 10s(5min 兜底) |
| connector  | GET `/health` :8082 / delay 20s / period 10s                               | GET `/health` :8082 / delay 5s / period 5s                                          | (无)                                                                       |

**关键点**:

- Java 端冷启动 ~30s(Spring context + JVM warm-up),必须配 `startupProbe` 兜底,否则 readinessProbe 会假阳性 fail
- `readinessProbe.failureThreshold` 严格(3 次失败 = 不进 endpoint)— 防"灰度"故障
- 详诊断见 `troubleshooting-runbook.md` §3 Readiness Probe Failed

---

## 5. HPA / PDB / NetworkPolicy / PrometheusRule

### 5.1 HPA(prod 启用)

```yaml
# values-prod.yaml(继承 base 1/5/80)
hpa:
  enabled: true
# values.yaml base
hpa:
  minReplicas: 1
  maxReplicas: 5
  targetCPU: 80
```

只对 `agent-core` deployment 生效。**bug 修复(Day 53 C)**:hpa.yaml template 之前引用 `targetCPUUtilizationPercentage`(values 没这个 key)→ 渲染为空 → HPA averageUtilization=null。Day 53 改为 `.Values.hpa.targetCPU` 单一字段名。

### 5.2 PDB(prod 启用)

```yaml
# values-prod.yaml
pdb:
  enabled: true
  minAvailable: 1
```

3 个 PDB:`agent-core` / `admin-bff` / `connector`(connector PDB 是 Day 53 C 新补,之前漏)。

`minAvailable: 1` 意味着 voluntary disruption(节点维护 / cluster autoscale)时,每个 service 至少保留 1 个 ready pod。

### 5.3 NetworkPolicy(prod 启用,Day 53 C 新增)

```yaml
networkPolicy:
  enabled: true
  ingressNamespace: ingress-nginx
```

6 个 NetworkPolicy 资源:

1. **default-deny** — 所有 pod 默认 ingress + egress 拒绝(网下基线)
2. agent-core ingress — 只接 ingress-nginx ns + admin-bff pod
3. admin-bff ingress — 只接 ingress-nginx ns + agent-core pod(:8080 + :9090)
4. connector ingress — 只接 agent-core pod
5. static-frontends ingress(admin-static/app-static)— 只接 ingress-nginx ns
6. egress-allow — kube-system DNS + 同 ns 任意 pod + 出站 :443 / :80

**前置**:cluster CNI 必须支持 NetworkPolicy(Calico / Cilium / kube-router)。Flannel 默认不支持。

### 5.4 PrometheusRule(prod 启用,Day 53 C 新增)

```yaml
prometheusRule:
  enabled: true
  tokenCostThresholdUsd: 50
```

7 个 alerts(详 `monitoring-alerts-sop.md` §4):

- HTTP 5xx > 1% / p99 > 2.5s / pod restart > 3/15min / OOM kill / CPU > 80% / LLM cost > $50/24h / chat fail > 5%

**前置**:cluster 装 kube-prometheus-stack(提供 PrometheusRule CRD)。原生 Prometheus 不识别。

---

## 6. 与 staging 的差异

| 配置                               | staging                                | prod                                   | 理由          |
| ---------------------------------- | -------------------------------------- | -------------------------------------- | ------------- |
| domain                             | `staging.agentcook.cc`                 | `agentcook.cc` / `demo.agentcook.cc`   | DNS 隔离      |
| TLS                                | `false`(自签或 staging cert)           | `true`(Cloudflare full strict)         | 真证书        |
| replicas                           | 全 1                                   | agent-core/admin-bff = 2               | HA            |
| HPA                                | off                                    | on(min=1 max=5)                        | 弹性          |
| PDB                                | off                                    | on(minAvailable=1)                     | 维护期保护    |
| NetworkPolicy                      | off                                    | on(default-deny + 6 allow)             | 隔离          |
| PrometheusRule                     | off                                    | on(7 alerts)                           | 告警          |
| sampler                            | 100%                                   | 0.1(10%)                               | 减 trace 体积 |
| resources(staging 减半,128Mi 起步) | 128Mi/100m → 256Mi/200m                | 256Mi/250m → 512Mi/500m(admin-bff 1Gi) | 真负载        |
| Secret                             | `--set` 命令行 / GitHub Actions secret | ExternalSecret / SealedSecret          | 安全          |
| log level                          | debug                                  | info                                   | 体积          |
| agentCore extraArgs                | (空)                                   | `--workers 4`                          | Day 50 C 调优 |
| admin-bff env                      | (空)                                   | Tomcat/HikariCP 4 项                   | D Day 51 调优 |

---

## 7. 启动顺序 + 部署 SOP

### 7.1 首次部署 prod(假设 cluster + CNI + kube-prometheus-stack 已就绪)

```bash
# 1. 创建 namespace + ResourceQuota + RBAC
kubectl create namespace agentcook-prod
kubectl label namespace agentcook-prod kubernetes.io/metadata.name=agentcook-prod
kubectl apply -f deploy/k8s/quota-prod.yaml          # CPU/mem 上限保护
kubectl apply -f deploy/k8s/rbac-prod.yaml           # ServiceAccount + Role(Day 53-54 buffer)

# 2. 部署 ExternalSecret 拉真凭证(假设 Vault 已配)
kubectl apply -f deploy/k8s/external-secrets-prod.yaml

# 3. 部署 PostgreSQL + Redis + etcd(StatefulSet,数据持久化)
helm install postgres-prod ./deploy/helm/postgres -n agentcook-prod \
  --set persistence.size=100Gi --set persistence.storageClass=ssd
helm install redis-prod bitnami/redis -n agentcook-prod \
  --set persistence.size=20Gi
helm install etcd-prod bitnami/etcd -n agentcook-prod

# 4. 等 DB ready(关键 — agentcook 启动时连 DB)
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=postgres -n agentcook-prod --timeout=300s
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=redis -n agentcook-prod --timeout=120s

# 5. 部署 agentcook 主体(blue 阶段,新 ns)
helm install agentcook-prod-blue ./deploy/helm/agentcook \
  -f deploy/helm/agentcook/values.yaml \
  -f deploy/helm/agentcook/values-prod.yaml \
  --namespace agentcook-prod-blue --create-namespace

# 6. 等所有 pod ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=agentcook-prod-blue -n agentcook-prod-blue --timeout=600s

# 7. 配 Ingress 指向 blue ns
kubectl apply -f deploy/k8s/ingress-blue.yaml

# 8. e2e 验证(详 §8)
```

### 7.2 升级(Blue-Green 滚动,详 ADR-006)

详 `k8s-operations-manual.md` §7。摘要:

1. 起 green ns 新版本
2. e2e + smoke test 验证
3. Cloudflare DNS 5% → 25% → 50% → 100% 渐进切流量(每阶段 5min 监控)
4. blue 保留 24h(秒级回滚)
5. 24h 后 `helm uninstall agentcook-prod-blue`

---

## 8. 健康验证 SOP

每次部署后必跑(可纳入 GitHub Actions cd-prod.yml gate):

```bash
# 1. 5 服务 endpoints 200
for svc in "agent-core:8000:/health" "admin-bff:8080:/actuator/health" "connector:8082:/health" "admin-static:80:/" "app-static:80:/"; do
  IFS=':' read -r name port path <<< "$svc"
  code=$(kubectl exec -n agentcook-prod deploy/agentcook-prod-${name} -- curl -s -o /dev/null -w "%{http_code}" "http://localhost:${port}${path}")
  echo "${name}${path}: ${code}"
done

# 2. JWT 拒绝路径(A01 access control 验证)
curl -i https://agentcook.cc/api/v1/agents/agt-001/identity        # 期望 401
curl -i -H "Authorization: Bearer fake" https://agentcook.cc/api/v1/users  # 期望 401

# 3. Grafana 3 dashboards 真有数据
# https://grafana.agentcook.cc/d/agentcook-overview
# https://grafana.agentcook.cc/d/agentcook-service-health
# https://grafana.agentcook.cc/d/agentcook-llm-metrics

# 4. 7 alerts 均处于 inactive(无误报)
kubectl get prometheusrules -n agentcook-prod
# Prometheus UI: https://prometheus.agentcook.cc/alerts

# 5. e2e Playwright 7 场景全 PASS
cd tests/e2e/playwright && npx playwright test --reporter=list
```

---

## 9. 容量规划

### 9.1 单 chat 真栈预估(Day 50 baseline 100u)

| 指标            |   实测 | 备注                                       |
| --------------- | -----: | ------------------------------------------ |
| chat 单次 token |     38 | qwen-turbo(76% 月预算 / 100u 30s baseline) |
| chat p95        | 1900ms | 含 100u 排队                               |
| chat p99        | 2300ms | 长尾                                       |
| chat RPS        |  27.73 | 30s × 100u baseline                        |

### 9.2 prod 容量目标

| 维度             | 目标                   |      当前(2 replicas) | 扩容触发(HPA)                                                                   |
| ---------------- | ---------------------- | --------------------: | ------------------------------------------------------------------------------- |
| chat RPS         | 100                    |         ~55(2× 27.73) | CPU > 80% → max=5 replicas                                                      |
| concurrent users | 500u(Day 50 mock 极限) |             200u 安全 | HPA 仅 CPU,QPS 监控加 PrometheusRule 后续                                       |
| 月 cost USD      | < $50                  | 100u 30s 测约 $0.0006 | LLM cost > $50/24h 触发 fallback chain(qwen-turbo → glm-4-flash → echo,ADR-016) |

### 9.3 满载场景(待 Phase 5 末 staging 重跑确认)

按 Day 50 推断:500u 并发时 admin-bff `:8080` Tomcat backlog 撞 connection reset(20 fail / 7.9%)。Day 51 D 调 threads=400 + accept-count=200 + HikariCP=30 后,500u 极限再测(Phase 5 末 buffer)。

---

## 9.4 数据库 Schema 迁移(Flyway 自动 / Day 56 评估结论)

**决策(Day 56 C)**:**不需要单独的 helm post-install Job 跑 migration**。理由:

1. Spring Boot admin-bff 启动时 Flyway 自动 baseline + migrate(`spring.flyway.enabled=true` 默认)— 见 `agentcook-java/agentcook-api/src/main/resources/application.yml:39`
2. 当前 V1-V4 全是 `ALTER TABLE ADD COLUMN` 或 `CREATE TABLE` non-destructive 操作,加列带 default + nullable,**对老 row 安全**
3. K8s 滚动更新策略:`maxSurge=1` `maxUnavailable=0` — 新版本 pod ready(Flyway migrate 完成 + healthcheck 通过)才 kill 旧 pod,migration 与流量天然解耦
4. 多 replica 场景:Flyway 内置 `flyway_schema_history` 锁(LOCK TABLE)防并发执行,2 个 admin-bff pod 同时启动也只有一个真 migrate

**何时需要 Job**(留 Phase 5 backlog):

- destructive migration(DROP COLUMN / DROP TABLE / 大批量 UPDATE)— 此时要先 scale admin-bff = 0 → 跑 Job → scale 回 N
- 数据迁移(不只 schema)— 几百万行回填,启动时长会拖慢 readiness gate

**ADR-018 V4 实测**(`db/migration/V4__add_quota.sql` D Day 56 落):

```sql
ALTER TABLE users ADD COLUMN free_questions_used  INTEGER     DEFAULT 0    NOT NULL;
ALTER TABLE users ADD COLUMN free_questions_quota INTEGER     DEFAULT 2    NOT NULL;
ALTER TABLE users ADD COLUMN quota_reset_at       TIMESTAMPTZ DEFAULT NULL;
```

3 列全 nullable 或带 default,符合"不要 Job"的判定,Flyway 自动跑即可。

---

## 10. 灾备 + 回滚

### 10.1 一键回滚

```bash
# helm 回滚到上一稳定版本
helm rollback agentcook-prod 0 --namespace agentcook-prod

# DNS 切回 blue(Blue-Green 期间)
bash scripts/dns-cutover.sh --target=blue
```

### 10.2 数据备份

| 数据       | 工具                               | 频率          | 保留  |
| ---------- | ---------------------------------- | ------------- | ----- |
| PostgreSQL | `pg_dump` 定时 cronjob → S3        | 每日 03:00    | 30 天 |
| Redis      | RDB snapshot + AOF                 | 每小时 + 实时 | 7 天  |
| etcd       | etcdctl snapshot                   | 每日 02:00    | 30 天 |
| LLM trace  | Langfuse 自托管 OR cloud retention | 实时          | 90 天 |

---

## 11. Day 53-54 落地清单(本文档随这次 commit)

- [x] HPA template 字段名 bug 修(`targetCPUUtilizationPercentage` → `targetCPU`)
- [x] connector PDB 新增(原只有 agent-core + admin-bff)
- [x] NetworkPolicy template 新增(6 资源:default-deny + 5 allow + egress)
- [x] PrometheusRule template 新增(1 资源 / 7 alerts / 3 group:http/pod/llm)
- [x] values-prod.yaml 加 networkPolicy + prometheusRule + agentCore extraArgs(--workers 4) + adminBff env(Tomcat 400 / accept 200 / HikariCP 30/5)
- [x] values-prod.yaml 修 adminBff limits 512Mi → 1Gi(同步 base 的 D Day 50 决策)
- [x] deployment-agent-core.yaml 加 args 段消费 extraArgs
- [x] deployment-java.yaml 加 env range 消费 adminBff.env
- [x] helm template 渲染验证全过(HPA=80 / args / env / 6 NP / 3 PDB / 7 alerts)
- [x] helm lint 0 failed
- [x] 本 production-configuration.md 起草

---

## 12. 给团队的注意事项

| 项                                             | 说明                                                         |
| ---------------------------------------------- | ------------------------------------------------------------ |
| **改 values-prod 必走 PR + Review**            | 不接受 `kubectl edit` 在线改(失去 IaC 留痕)                  |
| **新加 service 必写 NetworkPolicy**            | default-deny 模式,新 service 上不写 = 流量不进               |
| **新加 alert 必更新 monitoring-alerts-sop.md** | 留 runbook_url 链接到 troubleshooting-runbook.md             |
| **改 base values.yaml 影响 staging + prod**    | 必同步 review 两份 override 是否需要跟随 / override          |
| **JVM 参数变更走 image rebuild 还是 env?**     | 变 -Xmx 需 image / 变 spring 配置走 adminBff.env(免重 build) |

---

**最后更新**:2026-06-04 · Phase 5 Day 53 · Agent C
**配套**:`k8s-operations-manual.md` / `troubleshooting-runbook.md` / `monitoring-alerts-sop.md`
