# agentcook-domain

DDD Domain Layer — 纯业务逻辑，零框架依赖。

## 职责

- Aggregate Root 定义（User / Session / Plugin / Connector / Permission）
- Value Object（UserId / Email / SessionStatus 等）
- Domain Event（UserCreated / PluginRegistered 等）
- Repository 接口（Port 定义，实现在 infrastructure 层）
- Domain Service（跨聚合业务规则）

## 包结构

```
cc.agentcook.domain
├── user/          ← User 聚合
├── session/       ← Session 聚合
├── plugin/        ← Plugin 聚合
├── connector/     ← Connector 聚合
└── permission/    ← Permission 聚合
```

## 依赖关系

- **依赖**：仅 `jakarta.validation-api`（约束注解）
- **被依赖**：application / infrastructure 层

## 设计原则

- 聚合内强一致性，聚合间最终一致（通过 Domain Event）
- Repository 接口只定义业务语义方法，不暴露 JPA 细节
- Value Object 不可变，用 `record` 或 final class 实现
