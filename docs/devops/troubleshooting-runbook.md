# 故障排查 Runbook(agentcook)

> **目标读者**:on-call 工程师。本 runbook 覆盖 K8s 环境最常见的 5 类故障 — 每节给"症状 → 诊断 → 修复"三段式,并附跨语言诊断(Python uvicorn / Java Spring Boot Actuator / gRPC bridge)+ OTel trace 反查 + 紧急恢复 SOP。
>
> **配套**:
>
> - `k8s-operations-manual.md`(常用 kubectl + Helm 命令)
> - `monitoring-alerts-sop.md`(告警阈值 + 升级路径)
> - ADR-005 Observability · Day 50 perf report(p99 latency / token 消耗 baseline)

---

## 0. 故障分类速查表(2 分钟定位)

| 症状                                                                  | 诊断起点                                                               | 详见 |
| --------------------------------------------------------------------- | ---------------------------------------------------------------------- | ---- |
| Pod 不停重启,`STATUS=CrashLoopBackOff`                                | `kubectl describe pod` 看 events + `logs --previous` 看上次 crash 输出 | §1   |
| Pod `STATUS=OOMKilled` 或 `Last State: Terminated, Reason: OOMKilled` | `describe pod` + `dmesg` + JVM 端 `-Xlog:gc*` 对照 D Day 50 baseline   | §2   |
| Pod `READY 0/1` 长时间不进 ready                                      | `describe pod` 看 `Readiness probe failed:` events                     | §3   |
| Pod `STATUS=ImagePullBackOff` / `ErrImagePull`                        | `describe pod` 看 `Failed to pull image` events                        | §4   |
| Java pod p99 飙高 + GC 长                                             | Java Actuator `/actuator/metrics/jvm.gc.pause` + GC log + heap dump    | §5   |
| chat 接口 5xx 突增                                                    | OTel trace 反查异常 span(§6)+ Langfuse 看 LLM provider 失败            | §6   |
| 504 Gateway Timeout                                                   | Ingress / agent-core / admin-bff 链路逐段 curl(§7)                     | §7   |

---

## 1. CrashLoopBackOff

### 症状

```
NAME                                       READY   STATUS             RESTARTS   AGE
agentcook-prod-agent-core-7d8f6c5-x2k9p    0/1     CrashLoopBackOff   5          3m
```

`RESTARTS` 持续累加,Pod 启动几秒就 crash → kubelet 退避(10s → 20s → 40s → ... → 5min)再拉起。

### 诊断

```bash
# 1. 看 events(常见根因 9 成在这)
kubectl describe pod -n agentcook-prod <pod-name> | tail -40

# 2. 看上次 crash 的输出(最关键 — 当前 pod 还没起来 logs 没有,要 --previous)
kubectl logs -n agentcook-prod <pod-name> --previous --tail=200

# 3. 若是 init container 失败,要指定 -c
kubectl logs -n agentcook-prod <pod-name> -c <init-container-name> --previous

# 4. 进入旧的 ReplicaSet 找最近 deploy 改动(回滚目标)
kubectl rollout history -n agentcook-prod deployment/agentcook-prod-agent-core
```

### 5 类典型根因 + 修复

| 根因                  | 日志特征                                                                                       | 修复                                                                     |
| --------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| **环境变量缺失**      | `KeyError: 'AGENTCOOK_JWT_SECRET'` / `IllegalArgumentException: Could not resolve placeholder` | helm upgrade `--set secret.jwtSecret=...` 或 ExternalSecret 同步是否成功 |
| **DB 连接失败**       | `connection refused` / `OperationalError: could not connect`                                   | `kubectl get svc -A` 看 postgres svc 是否 Ready / firewall / DNS / 凭证  |
| **依赖服务未就绪**    | `gRPC: failed to connect to admin-bff:9090`                                                    | 加 init container 等 admin-bff ready,或调整 startup order                |
| **代码 startup 异常** | `Traceback / Exception in main thread`                                                         | logs --previous 看完整 stack,回滚 `kubectl rollout undo`                 |
| **OOM at startup**    | `MemoryError` / `Killed` 无栈 + `dmesg` 有 OOM                                                 | 提资源 limits(详 §2)                                                     |

### 紧急恢复

```bash
# 立刻回滚到上一稳定版本
kubectl rollout undo -n agentcook-prod deployment/agentcook-prod-agent-core

# 看是否 ready
kubectl rollout status -n agentcook-prod deployment/agentcook-prod-agent-core --timeout=2m
```

---

## 2. OOMKilled

### 症状

```
Last State:  Terminated
  Reason:    OOMKilled
  Exit Code: 137
  Started:   ...
  Finished:  ...
```

`Exit Code: 137` = 128 + SIGKILL(9)= cgroup memory limit 超出 → kernel kill。

### 诊断

```bash
# 1. 看哪个容器 OOM
kubectl describe pod -n agentcook-prod <pod-name> | grep -A 5 "Last State"

# 2. 看 limit 设了多少 — 跟 D Day 50 baseline 对照(adminBff 1Gi,agentCore 512Mi)
kubectl get pod -n agentcook-prod <pod-name> -o jsonpath='{.spec.containers[*].resources}' | jq

# 3. Python 端:看 RSS 真用量
kubectl exec -n agentcook-prod <pod-name> -- ps -eo rss,vsz,comm --sort=-rss | head

# 4. Java 端(admin-bff)— 看 GC log 是否 metaspace 涨 / heap 满
kubectl logs -n agentcook-prod <admin-bff-pod> --tail=500 | grep -E "GC|OutOfMemory|Heap"

# 5. 历史:本 pod 是否首次 OOM 还是反复
kubectl get events -n agentcook-prod --sort-by=.lastTimestamp | grep OOM
```

### 修复决策树

| 情况                           | 修复                                                                                                                                                |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Java admin-bff OOM(< 1Gi)      | D Day 50 已经把 limits 提到 1Gi + JVM `-Xmx768m`。继续 OOM = 真业务量级超预期 → 扩 replicas 或调到 2Gi                                              |
| Python agent-core OOM(< 512Mi) | 大概率内存泄露(asyncio task 堆积 / 大对象未释放)。先 dump heapsnapshot:`kubectl exec ... -- python -X tracemalloc -m ...`,贴入 Day 50 perf 模式排查 |
| metaspace OOM(Java only)       | `-XX:MaxMetaspaceSize=256m` 加 limit                                                                                                                |
| 短时 spike OOM                 | HPA 没生效 → §8 检查 HPA 状态                                                                                                                       |

### 紧急恢复

```bash
# 临时上调 limits(绕过 helm,事后用 helm upgrade 同步)
kubectl set resources deployment/agentcook-prod-admin-bff -n agentcook-prod \
  --limits=memory=2Gi --requests=memory=512Mi

# 或扩 replicas 分担负载
kubectl scale deployment/agentcook-prod-admin-bff -n agentcook-prod --replicas=4
```

---

## 3. Readiness Probe Failed

### 症状

```
NAME                                       READY   STATUS    RESTARTS   AGE
agentcook-prod-admin-bff-9c8d7-mpkq2       0/1     Running   0          2m
```

`STATUS=Running` 但 `READY=0/1` 卡住 → readinessProbe 持续失败 → Pod 不进 Service endpoint → Ingress 不路由流量 → 用户看到 503。

### 诊断

```bash
# 1. 看 events(关键)
kubectl describe pod -n agentcook-prod <pod-name> | grep -A 3 "Readiness"
# 期望看到:
#   Warning  Unhealthy  ...  Readiness probe failed: HTTP probe failed with statuscode: 503

# 2. 容器内 curl 自检
kubectl exec -n agentcook-prod <pod-name> -- curl -i http://localhost:8000/health
kubectl exec -n agentcook-prod <pod-name> -- curl -i http://localhost:8080/actuator/health

# 3. 看 probe 配置时序
kubectl get pod -n agentcook-prod <pod-name> -o yaml | grep -A 8 readinessProbe
```

### 5 类根因

| 根因                   | 验证                                  | 修复                                                                                     |
| ---------------------- | ------------------------------------- | ---------------------------------------------------------------------------------------- |
| **健康端点路径错**     | curl 返 404                           | helm upgrade 改 probe path(Java 是 `/actuator/health/readiness`,不是 `/actuator/health`) |
| **依赖未就绪**         | 端点返 503 + 业务日志 "DB not ready"  | 加 startupProbe 兜底 / 调长 initialDelaySeconds                                          |
| **冷启动太慢**         | initialDelaySeconds 太短              | Java 端用 startupProbe(failureThreshold=30 × 10s = 5 min 兜底,详 ops manual §6.2)        |
| **probe 自身 timeout** | events 写 "context deadline exceeded" | 加 `timeoutSeconds: 5`(默认 1s 太紧)                                                     |
| **业务真挂**           | logs 看异常                           | 同 §1 CrashLoopBackOff 处理                                                              |

### 紧急恢复

```bash
# 临时把 readinessProbe 改宽松(让 pod 进流量,但有"灰度"风险)
kubectl edit -n agentcook-prod deployment/agentcook-prod-admin-bff
# 改 readinessProbe.failureThreshold: 10 / timeoutSeconds: 10
```

---

## 4. ImagePullBackOff

### 症状

```
NAME                                       READY   STATUS             RESTARTS   AGE
agentcook-prod-agent-core-7d8f6c5-abc12    0/1     ImagePullBackOff   0          1m
```

### 诊断

```bash
# 1. 看 events 拉镜像失败原因(最关键)
kubectl describe pod -n agentcook-prod <pod-name> | grep -A 3 "Failed"
# 常见:
#   Failed to pull image "agentcook/agent-core:phase-5-rc1": rpc error:
#   ErrImagePull: pull access denied / manifest unknown / image not found

# 2. 自己拉一次验证
docker pull agentcook/agent-core:phase-5-rc1
# 或在节点上(若有 SSH):crictl pull ...

# 3. 看 imagePullSecrets 是否配
kubectl get sa default -n agentcook-prod -o yaml | grep -A 2 imagePullSecrets
```

### 修复表

| 根因                      | 修复                                                                                                                                                                           |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **tag 不存在 / 拼错**     | helm upgrade `--set agentCore.image.tag=phase-5-rc1`(看 CI 真出的 tag)                                                                                                         |
| **registry 认证失败**     | 创建 `kubectl create secret docker-registry agentcook-registry --docker-server=... --docker-username=... --docker-password=... -n agentcook-prod` + helm 注入 imagePullSecrets |
| **registry 不可达**(网络) | 排查 cluster 出口网络 / 防火墙 / DNS                                                                                                                                           |
| **image 太大,timeout**    | 提 kubelet `--image-pull-progress-deadline` 或拆 image / 用 multi-stage 减小                                                                                                   |

### 紧急恢复

```bash
# 回滚到上版本(原 image 本地有 cache,大概率拉得动)
kubectl rollout undo -n agentcook-prod deployment/agentcook-prod-agent-core
```

---

## 5. JVM heap OOM(D Day 50 已落 1Gi 后仍 OOM)

### 症状

```bash
kubectl logs <admin-bff-pod> --tail=200
# java.lang.OutOfMemoryError: Java heap space
# at java.util.HashMap.resize(HashMap.java:702)
# ...
```

或 GC log:`Pause Full (Allocation Failure)` 反复 + 每次回收量极小。

### 诊断(深度排查 SOP)

```bash
# 1. 拿当前 heap 占用
kubectl exec -n agentcook-prod <pod> -- jcmd 1 GC.heap_info

# 2. 看 GC log(D Day 50 已配 -Xlog:gc*:stdout:time)
kubectl logs <pod> | grep -E "Pause Young|Pause Full|GC\(" | tail -50

# 3. 出 heap dump(注意:dump 时 pod 会卡 ~30s,先扩 replicas)
kubectl scale -n agentcook-prod deployment/agentcook-prod-admin-bff --replicas=3
kubectl exec -n agentcook-prod <pod> -- jcmd 1 GC.heap_dump /tmp/heap.hprof
kubectl cp -n agentcook-prod <pod>:/tmp/heap.hprof /tmp/heap.hprof

# 4. 用 Eclipse MAT / VisualVM 分析(找 dominator tree top objects)
```

### 5 类典型根因

| 根因                                | heap dump 特征                          | 修复                                                                          |
| ----------------------------------- | --------------------------------------- | ----------------------------------------------------------------------------- |
| **JdbcTemplate 大查询不分页**       | `Object[]` 占 60%+                      | 改 Pageable + LIMIT                                                           |
| **HikariCP pool 持有 ResultSet**    | `Connection` 多个未释放                 | try-with-resources / 检查 `application.yml` `hikari.leak-detection-threshold` |
| **缓存无界增长**                    | `HashMap` / `ConcurrentHashMap` 占 50%+ | 用 Caffeine `maximumSize`                                                     |
| **session 持续累积**(WebSocket/SSE) | `Session` 数 = 在线用户 ×10+            | timeout 配置 + WebSocket idle 清理                                            |
| **真业务量超预期**                  | 各类对象均匀分布                        | 扩 replicas + JVM `-Xmx2g` + values-prod.yaml 同步                            |

### 紧急恢复

```bash
# 1. 扩 replicas 分担
kubectl scale -n agentcook-prod deployment/agentcook-prod-admin-bff --replicas=4

# 2. 临时上调 JVM heap(改 deployment env)
kubectl set env -n agentcook-prod deployment/agentcook-prod-admin-bff \
  JAVA_TOOL_OPTIONS="-Xmx1536m -XX:+AlwaysPreTouch -XX:+UseG1GC"

# 3. 后续 — 用 helm upgrade 同步 values-prod.yaml(留痕)
```

---

## 6. chat 5xx 突增(跨语言链路诊断)

链路:`Cloudflare → Ingress → agent-core(Python:8000)→ gRPC → admin-bff(Java:9090)→ DB / qwen API`

### 诊断 SOP(从外向内)

```bash
# 1. 看 Ingress 错误率(如有 ingress-nginx metrics)
kubectl exec -n ingress-nginx <controller-pod> -- curl -s http://localhost:10254/metrics | grep status=\"5

# 2. agent-core 端 — Python prometheus_client
kubectl exec -n agentcook-prod <agent-core-pod> -- curl -s http://localhost:8000/metrics | grep -E "http_requests_total|chat_"

# 3. admin-bff 端 — Spring Actuator
kubectl exec -n agentcook-prod <admin-bff-pod> -- curl -s http://localhost:8080/actuator/prometheus | grep -E "http_server_requests_seconds_count.*outcome=\"SERVER_ERROR\""

# 4. OTel trace 反查(Jaeger / Honeycomb / SigNoz)
# - service=agent-core 过滤 status_code=500
# - 看 span 树找异常段(qwen / gRPC / DB)

# 5. Langfuse 看 LLM provider 失败率(qwen rate limit / API key 失效)
# https://cloud.langfuse.com → traces 过滤 level=ERROR
```

### 6 类典型根因

| 根因                                | 信号                                                       | 修复                                                               |
| ----------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------ |
| **qwen API rate limit**             | Langfuse 看 429                                            | 切 fallback chain(qwen → echo,ADR-016)/ 联系阿里加配额             |
| **qwen API key 失效**               | Langfuse 看 401                                            | 更新 Secret + helm upgrade                                         |
| **DB 连接池打满**(HikariCP)         | Java logs `Connection is not available, request timed out` | 调 `hikari.maximum-pool-size`(D Day 51 已 30,可继续提)/ 检查慢 SQL |
| **gRPC bridge 异常**(Python ↔ Java) | trace span "gRPC: UNAVAILABLE"                             | port-forward admin-bff :9090 自测 grpcurl                          |
| **OTel collector 挂**(导致主链路慢) | 4317 timeout                                               | collector pod 重启 / 改 sampler 0.01 应急                          |
| **真上游故障**                      | 都正常但仍 5xx                                             | 看 cluster 节点 / etcd / kube-system 组件                          |

### 紧急恢复

```bash
# 1. fallback 切 echo(临时让用户能用)
kubectl set env -n agentcook-prod deployment/agentcook-prod-agent-core \
  AGENTCOOK_CHAT_PROVIDER_DEFAULT=echo

# 2. 加 replicas 分担
kubectl scale -n agentcook-prod deployment/agentcook-prod-agent-core --replicas=6

# 3. 看 HPA 是否真在扩(详 §8)
kubectl get hpa -n agentcook-prod
```

---

## 7. 504 Gateway Timeout

链路逐段 curl 定位卡哪段:

```bash
# 1. 公网入口
curl -i -w "\nT: %{time_total}s\n" https://demo.agentcook.cc/api/v1/agents/agt-001/identity

# 2. Cloudflare → Ingress(看 Cloudflare 仪表盘 5xx)

# 3. Ingress → Service
kubectl exec -n agentcook-prod <any-pod> -- curl -i -m 5 -w "\nT: %{time_total}s\n" \
  http://agentcook-prod-agent-core:8000/health

# 4. Service → Pod
kubectl exec -n agentcook-prod <any-pod> -- curl -i -m 5 -w "\nT: %{time_total}s\n" \
  http://<pod-IP>:8000/health
```

**修复决策**:

- 卡在 ④ → pod 真慢,看 §6 chat 5xx 路径
- 卡在 ③ → Service endpoints 没正确指向 pod(`kubectl get endpoints`)
- 卡在 ② → Ingress 配置(timeout / backend ssl)
- 卡在 ① → Cloudflare WAF / Bot Fight Mode 误伤

---

## 8. HPA 不伸缩

### 症状

CPU 100% 但 `kubectl get hpa` 显示 `REPLICAS=2`(没扩)。

### 诊断

```bash
# 1. 看 HPA 状态
kubectl describe hpa -n agentcook-prod agentcook-prod-agent-core-hpa

# 2. metrics-server 是否在跑(K8s 自带的 cluster metrics 提供方)
kubectl top nodes
kubectl top pods -n agentcook-prod
# 期望出数字,出 "Metrics API not available" 就是 metrics-server 没装
```

### 5 类根因

| 根因                              | 修复                                                                                                            |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| **metrics-server 没装**           | `kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml`   |
| **Pod 无 resources.requests.cpu** | HPA 算 utilization 必须有 requests — helm values 必须设(已设 250m)                                              |
| **HPA template bug**(本项目)      | Day 51 C 揪出:HPA template 引用 `targetCPUUtilizationPercentage`,values 写 `targetCPU` → 渲染为空。Day 53-54 修 |
| **maxReplicas 上限到了**          | values 提 maxReplicas                                                                                           |
| **scale stabilization 窗口**      | HPA 默认 scale-down 5min stabilization,等待即可                                                                 |

---

## 9. 通用紧急恢复 SOP

按"5 分钟内必做" → "30 分钟" → "事后复盘" 三层:

### 5 分钟内(止血)

1. `kubectl rollout undo`(若是发版后)
2. `kubectl scale --replicas=N+2`(扩容)
3. Cloudflare DNS 切回 blue(若 Blue-Green 中)

### 30 分钟内(根因)

1. logs / events / OTel trace / Langfuse 4 路定位
2. 找出根因后 helm upgrade 修(留痕,不要 kubectl edit)

### 事后(复盘)

1. 写 incident report(模板见 monitoring-alerts-sop.md §6)
2. 加 alerting 防同款再发
3. 更新本 runbook 加新场景

---

**最后更新**:2026-06-03 · Phase 5 Day 52 · Agent C
**配套**:`k8s-operations-manual.md` / `monitoring-alerts-sop.md` / Day 50 perf report / D Day 50 JVM heap commit ea0c5cb
