# agentcook-api

API Layer — REST 入口 + Spring Boot 主应用。

## 职责

- REST Controller（HTTP 端点暴露）
- Request/Response DTO（Day 24 由 OpenAPI spec 生成）
- OpenAPI 文档生成（springdoc-openapi → `/v3/api-docs`）
- Spring Security 配置（OAuth2 Resource Server + JWT）
- Spring Boot 主应用入口

## 包结构

```
cc.agentcook.api
├── controller/        ← @RestController 类
├── dto/               ← Request/Response DTO
├── config/            ← Security / OpenAPI / Web 配置（Day 23）
└── AgentcookJavaApplication.java
```

## 依赖关系

- **依赖**：`agentcook-application` + `agentcook-infrastructure`
- **被依赖**：无（顶层模块）

## 端点规划

| Path | 方法 | 说明 |
|------|------|------|
| `/api/v1/users/**` | CRUD | 用户管理 |
| `/api/v1/sessions/**` | CRUD | 会话管理 |
| `/api/v1/plugins/**` | CRUD | Plugin 注册 |
| `/api/v1/connectors/**` | CRUD | Connector 配置 |
| `/api/v1/permissions/**` | CRUD | RBAC 权限 |

## 运行

```bash
mvn spring-boot:run -pl agentcook-api
# 默认端口 8081
# Swagger UI: http://localhost:8081/swagger-ui.html
```
