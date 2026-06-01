# agentcook-swarm

微服务版本。Phase 4 将单体拆分为 4 个独立服务，通过 Traefik 网关统一入口。

## 服务架构

| 服务 | 职责 | 端口 | 技术栈 |
|------|------|------|--------|
| **gateway** | API 网关 + 路由 + 限流 | 80/9090 | Traefik v3 |
| **agent-core** | Chat/Stream + LLM 调度 + Memory | 8000 | Python FastAPI |
| **admin-bff** | 业务 CRUD(User/Plugin/Session/Connector/Permission) | 8080 | Java Spring Boot |
| **connector** | Plugin 执行沙箱 + 外部系统对接 | 8082 | Python |

## 通信方式

- **外部 → gateway**：HTTP/HTTPS + SSE
- **gateway → 服务**：HTTP（Phase 4.1），gRPC（Phase 4.2）
- **服务发现**：etcd（Phase 4.2），Phase 4.1 用 Docker DNS
- **可观测性**：OpenTelemetry → OTel Collector → Jaeger + Prometheus

## 快速启动（Phase 4）

```bash
docker-compose -f docker-compose.swarm.yml up -d
```

## 目录结构

```
agentcook-swarm/
├── docker-compose.swarm.yml    # 全栈编排
├── otel-collector-config.yaml  # OTel 采集器配置
├── services/
│   └── connector/              # Connector 微服务骨架
│       └── Dockerfile
└── README.md
```
