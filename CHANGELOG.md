# Changelog

All notable changes to **agentcook-cc** monorepo. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) + [Semantic Versioning](https://semver.org/).

## [Unreleased] — Phase 5 + Buffer

### Added
- **Phase 4.6** chat 端点接真 Qwen(ADR-017,提前 Phase 5 任务)— `agentcook/src/agentcook_app/routers/chat.py` `_stream_real_response` 替换 mock,SSE metadata 加 source / provider / output_chars / finish_reason
- **ADR-016** 默认 LLM Provider 切换到 Qwen qwen-turbo(`factory.py` `_DEFAULT_MODELS["qwen"]` plus → turbo)
- **ADR-017** chat 端点接真 LLM(Phase 4.6 决策完整留档)
- **ADR-018** 账号配额 + 分层模型(qwen-turbo → glm-4-flash 降级,v1 = 2 次/账号配置化)
- **Zhipu provider 实现**(`agentcook-providers/.../zhipu_provider.py` 109 行,智谱 OpenAI 兼容 endpoint,Day 9-10 跳过的最后一债 Day 53 补)
- **跨语言 IT**:`CrossLangIntegrationIT.java`(Java JWT → Python /chat/stream Bearer 透传)
- **API 版本管理**:`docs/api/VERSIONING-POLICY.md` 218 行 + `DEPRECATION-POLICY.md` 扩展到 282 行 + `CHANGELOG.md` 461 行
- **Java DDD 教学文档**:`agentcook-java/docs/ddd-guide.md` 494 行(配套教程 03 讲深度参考)
- **DevOps 文档 4 份**:`docs/devops/k8s-operations-manual.md` / `troubleshooting-runbook.md` / `monitoring-alerts-sop.md` / `production-configuration.md`(C Day 52-54)
- **架构图 3 张 mermaid**:`docs/architecture/01-overall / 02-chat-realtime-dataflow / 03-k8s-deployment`
- **6 包 README 完整版**:agentcook-core 154 / agentcook-providers 130 / agentcook-storage 161 / agentcook 165 / agentcook-swarm 149 / agentcook-starter 72 行 + admin 208 / app 284 / design-tokens 145 / java 194(11 README 全 ≥ 100 行)
- **配额机制实施**(ADR-018 cascade):
  - Java:Flyway `V4__add_quota.sql` + `UserAggregate.consumeFreeQuestion()` + `QuotaController` `/api/v1/quota`
  - Python:`agentcook/src/agentcook_app/middleware/quota.py` 150 行 + `chat.py` `_stream_real_response` 加 `provider_override` 参数
  - 前端:`ChatInput.tsx` + `useQuota` hook(待 B 补)
- **License**:MIT(开源 Agent Harness 主流选)

### Changed
- `pom.xml`:加 `org.owasp:dependency-check-maven` 10.0.4 plugin(D Day 51 OWASP A06)
- `pyproject.toml`:加 `[build-system]` + `[tool.setuptools] packages=[]`(防 Cloudflare Pages pip auto-install fail,Phase 4.6 cookbook 坑 2)
- `application.yml`:Tomcat `accept-count` 100 → 200 + HikariCP `maximum-pool-size` 10 → 30(D Day 51,C Day 50 调优 #1 推荐值)
- `Dockerfile` (agentcook-java):JAVA_OPTS 加 `-XX:+AlwaysPreTouch` + `-Xlog:gc*` + `-XX:+HeapDumpOnOOM`(D Day 50)
- `deploy/helm/agentcook/values.yaml`:agentCore `extraArgs: ["--workers", "4"]` + adminBff memory 512Mi → 1Gi(C Day 50 / A Day 52)
- `factory.py`:`_DEFAULT_MODELS["qwen"]` plus → turbo(ADR-016)+ NotImplementedError 去掉 + zhipu 真分支(A Day 53)

### Fixed
- **Plugin 沙箱 caller bug**(`poc/plugin-sandbox/sandbox_runner.py:86` 传 `container_name` 但定义为 0 参数 → TypeError,Phase 0 遗留,C Day 51 修通)
- **Python 4 高危 CVE**:cryptography 46.0.0 → 45.0.7(PYSEC-2026-36/35 + CVE-2026-26007)+ starlette 1.0.0 → 1.2.1(PYSEC-2026-161)— C Day 51 OWASP A06 当天修
- **前端 hardcode baseURL 触发 CORS**(P1 cookbook 坑 6,4 文件 6 处)— vite proxy 路径配置化
- **router 无 auth guard**(P1 cookbook 坑 7)— LoginPage useEffect navigate 临时方案

### Security
- **OWASP Top 10 自检清单**(C Day 51):8 ✅ + A02 🟡(prod fail-fast)+ A04 🔴(rate limit / Phase 5 backlog #11)
- **Plugin 沙箱 5 检测向量**:4 真 BLOCK + 2 test 设计 bug + **0 真泄露**
- **跨语言 JWT 边界**:Python 4 + Java 5 = 9/9 PASS

### Removed
- mock chat hardcode 字符串(协调员 brief 假设但 Pact v3 mock 设计就不断言 SSE,A Day 48-49 fact-check 揪)

---

## Phase 0-3 历史(简略,详 _internal/progress/ 50+ 份 progress)

### Phase 0(Day 1-5)— 架构准备
- 13 ADR(ADR-001 ~ ADR-013)+ 6 protocol 抽象(Tool / Skill / Plugin / Connector / LLMProvider / Agent)
- Plugin Docker 沙箱 POC(5 隔离检测向量)
- LangGraph 集成 POC(声明式 router → StateGraph)
- v6.0 升级:agentcook-core / providers / storage / swarm / Java 多包架构

### Phase 1(Day 6-15)— 核心包拆分 + 后端基础
- agentcook-core(6 protocol Python 实现)
- agentcook-providers(OpenAI / Qwen 复用 / Echo / Fallback)
- agentcook-storage(PostgreSQL + pgvector + Redis)
- agentcook 主壳(FastAPI + JWT 双 token + 5 router)
- 协调员失误清算 5 次(decisions-2026-05-29-coordinator-failures.md)

### Phase 2(Day 16-25)— Agent Core + Java DDD 意外
- ADR-013 Java 业务后端(Day 11 CF-3 后启动,DDD 4 层 + 5 聚合)
- ADR-011 Agent 记忆体系(Identity / Soul / Memory / Diary 4 层栈)
- multi-agent LangGraph 集成
- Phase 2 review + 集成测试 + LLM Observability

### Phase 3(Day 26-37)— Admin + App 前端
- agentcook-admin(Vue 3 + Element Plus + Pinia)
- agentcook-app(React 19 + Tailwind + shadcn/ui + Electron)
- agentcook-design-tokens(Style Dictionary + Storybook 8)
- 双端 i18n + chat 流式 SSE
- 接管 AI 接管 Day 32-40(Audit 检查清单制度化)

### Phase 4(Day 38-47)— 微服务 + Observability + 上线准备
- agentcook-swarm(6 微服务 + gateway + etcd + OTel)
- Helm chart(11 templates × 3 deployment)
- ADR-005 Observability 全栈(OTel + Jaeger + Prometheus + Langfuse + Loki)
- ADR-006 Blue-Green deployment(staging + prod 双环境)
- Pact contract 测试 8 个 + broker 自托管
- Phase 4 GO/NO-GO 推荐(2026-05-22)
- **Phase 4.5 真上线推迟到教程发布前(P2 路线,2026-06-01 作者拍板)**

---

## Phase 5(Day 48-57)— 测试 + 文档 + 收尾

### Phase 5a 测试金字塔(Day 48-49)
- 4 层测试金字塔最终验证(unit + integration + contract Pact + e2e Playwright)
- agentcook-app vitest 39 PASS + cross-browser e2e 5 场景 × 2(Chromium + Firefox,WebKit Phase 5 buffer)
- Java 92.3% line coverage / 84.2% 4 模块聚合
- 协调员 brief 偏差 6 处被 A/B/D fact-check 揪(cookbook 坑 23 制度化)

### Phase 5b 性能 + 调优(Day 50)
- chat 真栈 100u qwen-turbo baseline + 200u/500u mock 极限
- uvicorn 1→4 workers 调优(login p95 -47% / login fail -95%)
- webvitals-under-load 4 数据点曲线(B 揪 TTFB +291% 最敏感)

### Phase 5c 合规检查(Day 51)
- OWASP Top 10 自检清单 8 ✅ + 2 flag
- Plugin 沙箱 0 真泄露
- JWT 9/9 边界 PASS
- Phase 5 GO/NO-GO 推荐 GO

### Phase 5d 文档 + 配额机制(Day 52-54)
- API 版本管理 + Deprecation Policy + Versioning Policy 完整
- 11 README 全 ≥ 100 行
- 9 ADR 复盘(A 233 行)
- ADR-018 配额机制起草 + Zhipu provider 实现
- 架构图 3 mermaid

### Phase 5e 终极段(Day 55-57)
- demo 5 min 视频(B 主笔 + A/C/D 配合录制段)
- 附录 C 建造编年体精华版起草(协调员 Buffer Day 58 主战)
- 第 33 讲 Harness Engineering(作者 Buffer Day 58 主笔)
- ADR-018 实施 cascade(D Java + A Python + B 前端)
- Phase 5 review + GO/NO-GO 决策书

---

## Buffer(Day 58-65)— Phase 5 完成后

详 `_internal/progress/integration-brief-day-55-57.md` "Buffer Day 58-65 计划"。

---

## Source

- 完整变更日志:`_internal/progress/` 50+ 份 progress + `_internal/audit/` 25+ 份 audit
- ADR 索引:`docs/adr/ADR-001` ~ `ADR-018`
- API CHANGELOG:`docs/api/CHANGELOG.md`(API 版本变更细节)
