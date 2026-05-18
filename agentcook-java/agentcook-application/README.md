# agentcook-application

Application Layer — 用例编排 + 事务边界。

## 职责

- Use Case（Application Service）编排 domain 层操作
- 事务管理（`@Transactional` 边界在此层）
- DTO 组装（MapStruct domain ↔ DTO 转换）
- 应用级校验（跨聚合前置检查）

## 包结构

```
cc.agentcook.application
└── usecase/
    ├── CreateUserUseCase
    ├── RegisterPluginUseCase
    ├── CreateSessionUseCase
    ├── ConfigureConnectorUseCase
    └── GrantPermissionUseCase
```

## 依赖关系

- **依赖**：`agentcook-domain`（聚合 + Repository 接口）
- **被依赖**：`agentcook-api`（Controller 调用 Use Case）

## 设计原则

- 一个 Use Case = 一个业务场景（不做 God Service）
- 事务边界在 Use Case 方法级别
- 不直接依赖 infrastructure 细节（通过 domain Repository 接口间接）
