# ADR-004: Plugin 沙箱 v1 使用 Docker Container 隔离

## Status

Accepted (2026-05-16)

## Context

Plugin 系统允许用户上传并执行自定义 Python 代码（scripts/ 目录），属于高危操作。若未规划完善的安全隔离模型，可能导致：
- 宿主机文件系统被篡改
- 敏感环境变量泄露
- 恶意网络请求（数据外传、DDoS）
- 资源耗尽攻击（CPU/内存无限占用）

## Decision

v1 版本采用 **Docker Container** 作为 Plugin 执行沙箱，每次调用 scripts/ 时启动 ephemeral container。

### 资源限制
- CPU：0.5 核
- 内存：512MB
- 执行超时：30 秒

### 网络限制
- 默认禁止所有出站流量
- 仅允许访问 `plugin.json` 中声明的 connector 域名白名单

### 文件系统
- 根文件系统只读挂载（`--read-only`）
- 工作区使用 tmpfs 临时文件系统，容器销毁后数据自动清除
- Plugin 代码通过 volume 只读挂载进入容器

### 安全加固
- 以 non-root 用户身份运行（UID 1000）
- 启用 `--no-new-privileges` 禁止提权
- 禁用所有 Linux capabilities（`--cap-drop=ALL`）

### 升级路径
- v1.1 评估 WASM（wasmtime/wasmer）方案，降低冷启动延迟
- v2.0 考虑 gVisor 或 Firecracker microVM，提供更强隔离级别

## Consequences

### Positive
- **隔离级别高**：Docker namespace + cgroups 提供进程、网络、文件系统级别的完整隔离
- **实现成本低**：Docker SDK 成熟，团队熟悉度高，无需自研沙箱运行时

### Negative
- **冷启动延迟**：首次调用需拉取镜像并启动容器，延迟约 1-2 秒（可通过镜像预加载优化）
- **基础设施依赖**：宿主机必须安装 Docker daemon，K8s 环境需适配 containerd
