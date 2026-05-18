## Plugin Docker 沙箱设计

### 设计目标
隔离 Plugin 可执行脚本，防止恶意代码影响宿主机。通过 Docker 容器提供轻量级运行时隔离，确保插件代码在受限环境中执行。

### 隔离机制

- **Docker ephemeral container**：使用 `--rm` 参数，容器执行完毕后自动清理，不留残留
- **只读 rootfs + tmpfs 工作区**：根文件系统设为只读（`--read-only`），仅允许在 `/tmp` 等 tmpfs 挂载点写入
- **非 root 用户**：容器内以 `sandbox` 用户身份运行，避免提权风险
- **禁止提权**：启用 `--security-opt=no-new-privileges`，阻止 setuid/setgid 等操作

### 资源限制

| 维度 | 限制 |
|---|---|
| CPU | 0.5 核 |
| 内存 | 512MB |
| 执行时间 | 30 秒 |
| 磁盘（tmpfs）| 64MB |
| 网络 | 默认 none，可声明白名单域名 |

### 攻击向量测试

| 攻击场景 | 预期结果 |
|---|---|
| 读取宿主机密文件（/etc/passwd） | 返回容器内隔离的 passwd，不含宿主用户信息 |
| 发起外部网络请求 | 连接被阻断（--network=none） |
| CPU 死循环耗尽资源 | 超时终止（timeout 30s） |
| 内存无限分配导致 OOM | OOM Killer 终止或捕获 MemoryError |
| 写入宿主文件系统 | 只读文件系统拒绝写入操作 |

### Bypass 风险评估

- **Docker escape CVE**：需及时更新 Docker 版本，修复已知容器逃逸漏洞
- **共享 kernel 攻击面**：Linux 内核漏洞可能被利用，需保持内核补丁更新
- **container breakout**：/proc、/sys 等敏感挂载点可能被滥用，已通过只读挂载缓解
- **网络白名单 DNS 绕过**：当前 POC 为简化实现，生产环境需引入 eBPF 或代理层进行细粒度控制
- **缓解措施**：定期更新 Docker/内核、遵循最小权限原则、配置 seccomp profile 限制系统调用

### 升级路径

- **v1.1**：gVisor（user-space kernel）—— 提供更强的内核隔离，减少共享内核攻击面
- **v1.2**：WASM（Wasmtime / WasmEdge）—— 基于 WebAssembly 的沙箱，启动更快、资源开销更低
- **v2.0**：Firecracker microVM（AWS Lambda 同款）—— 硬件级虚拟化隔离，安全性最高，适合高敏感场景
