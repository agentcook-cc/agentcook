# agentcook-swarm

微服务版。gateway + agent/skills/connector/admin 4 服务。gRPC + etcd + Traefik。类比 mall-swarm。

## 服务架构

- gateway: API 网关
- agent: Agent 服务
- skills: Skills 服务
- connector: Connector 服务
- admin: 管理服务

## 技术栈

- gRPC
- etcd 服务发现
- Traefik 反向代理
