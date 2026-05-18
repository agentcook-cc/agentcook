# agentcook-infrastructure

Infrastructure Layer — 技术实现细节。

## 职责

- JPA Repository 实现（实现 domain 层的 Repository 接口）
- Flyway 数据库迁移
- Redis 缓存适配
- gRPC client（调用 Python AgentRuntimeService）
- 外部服务集成

## 包结构

```
cc.agentcook.infrastructure
├── persistence/       ← JPA Entity + Repository 实现
├── cache/             ← Redis 缓存适配（Day 22）
└── grpc/              ← gRPC client to Python（Day 35）
```

## 依赖关系

- **依赖**：`agentcook-domain`（实现 Repository 接口）
- **被依赖**：`agentcook-api`（组装 Spring Context）

## Flyway Migrations

```
src/main/resources/db/migration/
└── V1__init.sql       ← Day 22 填充（5 张表）
```

## 设计原则

- JPA Entity ≠ Domain Aggregate（Entity 是持久化模型，做 mapping）
- Repository 实现内部可用 Spring Data 便捷方法
- 外部集成做防腐层（Anti-Corruption Layer）
