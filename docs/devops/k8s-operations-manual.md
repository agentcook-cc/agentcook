# K8s 运维手册(agentcook)

> **目标读者**:on-call 工程师 / DevOps / SRE。本手册覆盖 agentcook 在 K8s 环境的日常运维操作 — Helm chart 管理、kubectl 速查、滚动更新、Blue-Green 切流量、namespace 隔离、Secret 管理、RBAC 配置。
>
> **配套文件**:
>
> - `troubleshooting-runbook.md`(故障排查 5 大场景)
> - `monitoring-alerts-sop.md`(告警 + on-call SOP)
> - `production-configuration.md`(生产配置完整清单 / Day 53-54 起草)
> - ADR-005(Observability)· ADR-006(Blue-Green)· ADR-007(测试金字塔)

---

## 1. 服务架构速览(5 个 Deployment)

| 服务           | 镜像                     |                      端口 | 协议        | 角色                                                                                                  |
| -------------- | ------------------------ | ------------------------: | ----------- | ----------------------------------------------------------------------------------------------------- |
| `agent-core`   | `agentcook/agent-core`   |                    `8000` | HTTP        | Python FastAPI 主壳 / `/api/v1/agents/*` `/skills/*` `/memory/*` `/chat`(SSE)                         |
| `admin-bff`    | `agentcook/admin-bff`    | `8080` HTTP / `9090` gRPC | HTTP + gRPC | Java Spring Boot / `/api/v1/users` `/sessions` `/plugins` `/connectors` `/permissions` + gRPC chat 桥 |
| `connector`    | `agentcook/connector`    |                    `8082` | HTTP        | Python OAuth/Webhook/HTTP 外置插件路径                                                                |
| `admin-static` | `agentcook/admin-static` |                      `80` | HTTP        | nginx 静态托管 admin SPA                                                                              |
| `app-static`   | `agentcook/app-static`   |                      `80` | HTTP        | nginx 静态托管 app SPA                                                                                |

**资源请求**(values-prod.yaml,Day 50/51 调优后):

| 服务         | replicas | requests     | limits                               |
| ------------ | -------: | ------------ | ------------------------------------ |
| agent-core   |        2 | 256Mi / 250m | 512Mi / 500m                         |
| admin-bff    |        2 | 256Mi / 250m | **1Gi**(D Day 50 ea0c5cb 调升)/ 500m |
| connector    |        1 | 256Mi / 250m | 512Mi / 500m                         |
| admin-static |        1 | 128Mi / 100m | 256Mi / 200m                         |
| app-static   |        1 | 128Mi / 100m | 256Mi / 200m                         |

**Java 端 JVM heap**:`-Xmx768m -XX:+AlwaysPreTouch -XX:+UseG1GC -Xlog:gc*:stdout:time` (D Day 50,留 ~256Mi headroom 给 metaspace + 直接内存)。

---

## 2. Helm chart 速查

Chart 路径:`deploy/helm/agentcook/`(monorepo 根)/ 3 values 文件 / 11 templates。

### 2.1 install / upgrade / rollback

```bash
# 首次安装(staging)
helm install agentcook-staging ./deploy/helm/agentcook \
  -f deploy/helm/agentcook/values.yaml \
  -f deploy/helm/agentcook/values-staging.yaml \
  --namespace agentcook-staging --create-namespace \
  --set secret.dbPassword="$STAGING_DB_PWD" \
  --set secret.jwtSecret="$STAGING_JWT_SECRET"

# 升级(替换 image tag)
helm upgrade agentcook-staging ./deploy/helm/agentcook \
  -f deploy/helm/agentcook/values.yaml \
  -f deploy/helm/agentcook/values-staging.yaml \
  --set agentCore.image.tag=phase-5-rc1 \
  --set adminBff.image.tag=phase-5-rc1 \
  --reuse-values \
  --namespace agentcook-staging

# 查看 release 历史
helm history agentcook-staging --namespace agentcook-staging

# 回滚到上一版本
helm rollback agentcook-staging 0 --namespace agentcook-staging
helm rollback agentcook-staging 3 --namespace agentcook-staging  # 回滚到 revision 3

# 卸载
helm uninstall agentcook-staging --namespace agentcook-staging
```

### 2.2 dry-run + diff(改前必跑)

```bash
# 渲染 manifest 不部署 — 看 image tag / replicas / env 是否符合预期
helm template agentcook-prod ./deploy/helm/agentcook \
  -f deploy/helm/agentcook/values.yaml \
  -f deploy/helm/agentcook/values-prod.yaml > /tmp/prod-manifest.yaml
grep -E "image:|replicas:|OTEL_" /tmp/prod-manifest.yaml | head -30

# Diff with cluster(需安装 helm-diff plugin:helm plugin install https://github.com/databus23/helm-diff)
helm diff upgrade agentcook-prod ./deploy/helm/agentcook \
  -f deploy/helm/agentcook/values.yaml \
  -f deploy/helm/agentcook/values-prod.yaml
```

### 2.3 三 values 文件分工

| 文件                  | 用途            | 关键差异                                                                                       |
| --------------------- | --------------- | ---------------------------------------------------------------------------------------------- |
| `values.yaml`         | base / dev 默认 | replicas=1 / hpa.enabled=false / pdb.enabled=false / sampler 100%                              |
| `values-staging.yaml` | staging         | resources 减半(128Mi 起步)/ domain=staging.agentcook.cc                                        |
| `values-prod.yaml`    | prod            | replicas agent-core/admin-bff=2 / hpa.enabled=true / pdb.enabled=true / sampler 0.1 / tls=true |

**注**:Day 53-54 C 待补:① values-prod.yaml 加 `agentCore.extraArgs: ["--workers", "4"]`(C Day 50 ping A 推荐)② 加 Tomcat/HikariCP 调优(D Day 51 application.yml 已落,prod 同步)③ HPA template 字段名 bug `targetCPUUtilizationPercentage` vs values `targetCPU`(渲染会空,需对齐)。

---

## 3. kubectl 常用 9 命令

```bash
# 1. 看 pods 状态(看 ready / restarts / age)
kubectl get pods -n agentcook-prod -o wide
kubectl get pods -n agentcook-prod -l app.kubernetes.io/component=agent-core

# 2. 看日志(实时 + tail)
kubectl logs -n agentcook-prod -l app.kubernetes.io/component=agent-core -f --tail=100
kubectl logs -n agentcook-prod <pod-name> -c <container> --since=10m

# 3. describe(看 events / probe 失败原因)
kubectl describe pod -n agentcook-prod <pod-name> | tail -40

# 4. exec 进容器(诊断)
kubectl exec -it -n agentcook-prod <pod-name> -- /bin/sh
kubectl exec -n agentcook-prod <pod-name> -- env | grep OTEL

# 5. port-forward(本地访问 cluster 内服务,绕过 Ingress)
kubectl port-forward -n agentcook-prod svc/agentcook-prod-agent-core 8000:8000
# 然后本地 curl http://localhost:8000/health

# 6. rollout 状态 / 历史 / 重启 / 撤销
kubectl rollout status -n agentcook-prod deployment/agentcook-prod-agent-core
kubectl rollout history -n agentcook-prod deployment/agentcook-prod-agent-core
kubectl rollout restart -n agentcook-prod deployment/agentcook-prod-agent-core
kubectl rollout undo -n agentcook-prod deployment/agentcook-prod-agent-core --to-revision=2

# 7. scale(临时调 replicas,HPA 启用时优先用 HPA)
kubectl scale -n agentcook-prod deployment/agentcook-prod-agent-core --replicas=4

# 8. edit 在线改(谨慎,会绕过 Helm — 推荐 helm upgrade)
kubectl edit -n agentcook-prod deployment/agentcook-prod-agent-core

# 9. delete pod(让 ReplicaSet 重建,常用于触发重新调度)
kubectl delete pod -n agentcook-prod <pod-name>
```

**速记口诀**:`get → describe → logs → exec`(80% 故障靠这 4 步定位)。

---

## 4. namespace 隔离

```bash
# 创建 namespace
kubectl create namespace agentcook-staging
kubectl create namespace agentcook-prod

# 设当前 context 默认 ns(避免每次 -n 参数)
kubectl config set-context --current --namespace=agentcook-prod

# ResourceQuota — 防 staging 撑爆共享 cluster
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ResourceQuota
metadata:
  name: agentcook-staging-quota
  namespace: agentcook-staging
spec:
  hard:
    requests.cpu: "4"
    requests.memory: "8Gi"
    limits.cpu: "8"
    limits.memory: "16Gi"
    persistentvolumeclaims: "5"
EOF
```

**约定**:

- `agentcook-staging` — staging.agentcook.cc 跑预发布 e2e
- `agentcook-prod` — demo.agentcook.cc 真生产
- `agentcook-prod-blue` / `agentcook-prod-green` — Blue-Green 部署期间双 ns(详 §7)

---

## 5. RBAC + Secret 管理

### 5.1 Secret 选型决策树

| 场景       | 选型                                             | 工具                          |
| ---------- | ------------------------------------------------ | ----------------------------- |
| 本地 dev   | values.yaml 明文(`dev-only-do-not-use-in-prod`)  | 直接 helm install             |
| staging    | 手动 `--set secret.dbPassword=...`               | CI 注入 GitHub Actions secret |
| prod(推荐) | **ExternalSecret + Vault / AWS Secrets Manager** | external-secrets-operator     |
| prod(轻量) | **SealedSecret**(加密后 commit 进 git)           | bitnami-labs/sealed-secrets   |

### 5.2 SealedSecret 实操

```bash
# 1. 安装 controller(只在 cluster 上跑一次)
helm repo add sealed-secrets https://bitnami-labs.github.io/sealed-secrets
helm install sealed-secrets sealed-secrets/sealed-secrets -n kube-system

# 2. 拿 cluster 公钥
kubeseal --fetch-cert > /tmp/sealed-secret.cert

# 3. 把 plain Secret 加密
kubectl create secret generic agentcook-prod-secret \
  --from-literal=dbPassword="$REAL_PWD" \
  --from-literal=jwtSecret="$REAL_JWT" \
  --dry-run=client -o yaml | \
  kubeseal --cert /tmp/sealed-secret.cert -o yaml > deploy/helm/agentcook/templates/sealed-secret.yaml

# 4. commit(密文,安全)
git add deploy/helm/agentcook/templates/sealed-secret.yaml
git commit -m "ops: agentcook-prod sealed secret"

# 5. helm 部署时 controller 自动解密成真 Secret
```

### 5.3 RBAC ServiceAccount + Role(最小权限)

```yaml
# deploy/helm/agentcook/templates/rbac.yaml(Day 53-54 待补)
apiVersion: v1
kind: ServiceAccount
metadata:
  name: agentcook-app
  namespace: agentcook-prod
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: agentcook-app-role
  namespace: agentcook-prod
rules:
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list", "watch"] # 只读,不允许 write
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: agentcook-app-binding
  namespace: agentcook-prod
roleBinding:
  - kind: ServiceAccount
    name: agentcook-app
roleRef:
  kind: Role
  name: agentcook-app-role
  apiGroup: rbac.authorization.k8s.io
```

---

## 6. 滚动更新策略

`Deployment.spec.strategy`(默认 `RollingUpdate`):

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1 # 临时多创建 1 个 pod(2 replicas → 上限 3)
    maxUnavailable: 0 # 不允许任何 pod 同时不可用 — 严格零停机
```

### 6.1 readinessProbe 是滚动更新的 gate

```yaml
readinessProbe:
  httpGet:
    path: /health # Python: /health(agent-core:8000)
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
  failureThreshold: 3
  timeoutSeconds: 3
```

**关键**:`readinessProbe` 失败 → pod 不进 Service endpoint → Service 不路由流量 → 滚动更新 controller 等到新 pod ready 才 kill 旧 pod。

### 6.2 Java 端启动慢的处理

Spring Boot 冷启动 ~30s(JVM warm-up + Spring context),需把 `initialDelaySeconds` 设到 30+ 或用 `startupProbe`:

```yaml
startupProbe:
  httpGet:
    path: /actuator/health
    port: 8080
  failureThreshold: 30 # 30 × 10s = 5 分钟兜底
  periodSeconds: 10
readinessProbe:
  httpGet:
    path: /actuator/health/readiness
    port: 8080
  periodSeconds: 5
```

---

## 7. Blue-Green 部署 SOP(引用 ADR-006)

### 7.1 流程

1. **green 部署**:`helm install agentcook-prod-green ./deploy/helm/agentcook -f values-prod.yaml --set image.tag=phase-5-rc1 --namespace agentcook-prod-green --create-namespace`
2. **e2e 验证**:在 green ns 跑 `tests/e2e/playwright/`(7 场景全 PASS)+ `staging-smoke.sh` + 手工抽查 5 endpoint 200
3. **渐进切流量**:Cloudflare DNS A 记录从 blue 切 green,按 5% → 25% → 50% → 100% 4 阶段(每阶段守 5 min 监控 5xx + p99 latency,任一超阈值立刻回切 blue)
4. **24h 保留 blue**:`helm uninstall agentcook-prod-blue` **延后** 24h(秒级回滚兜底)
5. **24h 后清理**:`helm uninstall agentcook-prod-blue --namespace agentcook-prod-blue` + `kubectl delete namespace agentcook-prod-blue`

### 7.2 回滚(发现问题时)

```bash
# 立刻 — Cloudflare DNS 把 A 记录切回 blue(< 1 分钟生效)
# 然后 — green 保留 24h 等问题诊断完再清,或者
helm uninstall agentcook-prod-green --namespace agentcook-prod-green
kubectl delete namespace agentcook-prod-green
```

### 7.3 Cloudflare DNS 切换命令(自动化脚本)

```bash
# scripts/dns-cutover.sh — 用 Cloudflare API
# 需 export CF_API_TOKEN + CF_ZONE_ID
curl -X PUT "https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID/dns_records/$RECORD_ID" \
  -H "Authorization: Bearer $CF_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data "{\"type\":\"A\",\"name\":\"demo.agentcook.cc\",\"content\":\"$GREEN_IP\",\"ttl\":60,\"proxied\":true}"
```

---

## 8. 常见维护任务

| 任务                        | 频率 | 命令                                                                 |
| --------------------------- | ---- | -------------------------------------------------------------------- |
| 看 pod 重启次数(早发现 OOM) | 每天 | `kubectl get pods -A -o wide \| awk '$5>0 {print}'`                  |
| 检查 HPA 是否在伸缩         | 每周 | `kubectl get hpa -A`                                                 |
| Helm release 健康度         | 每周 | `helm list -A` 应全部 `STATUS=deployed`                              |
| K8s API server cert 过期    | 季度 | 看 cert-manager 自动续期 / kubeadm certs check-expiration            |
| Prometheus retention 检查   | 每周 | `kubectl exec ... -- df -h /prometheus`(详 monitoring-alerts-sop.md) |

---

## 9. 与教程章节交叉引用

| 文档                       | 关联教程章节                                                       |
| -------------------------- | ------------------------------------------------------------------ |
| 本手册 §2-3 Helm + kubectl | `chapters/05-deployment-and-ops.md`(Phase 4 末)                    |
| §7 Blue-Green              | `chapters/05-deployment-and-ops.md` § Blue-Green 段                |
| §5 Secret 管理             | `chapters/06-security-and-compliance.md` § Secret 章节(Phase 5 写) |

---

**最后更新**:2026-06-03 · Phase 5 Day 52 · Agent C(DevOps + 测试)
**变更记录**:

- 2026-06-03 Day 52:首版(C 主笔)
- (Day 53-54)Helm 完善 commit 后回填 §2.3 待补项
