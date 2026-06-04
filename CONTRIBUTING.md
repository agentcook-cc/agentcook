# Contributing to AgentCook

感谢你想贡献 AgentCook!这份指南讲清楚 3 件事:1) 怎么开 issue / PR / discussion 2) 代码 / 测试 / 风格规范 3) 维护者响应承诺。

---

## 1. 报 bug / 提 feature / 问问题 / 报文档错

请用对应的 issue 模板(`.github/ISSUE_TEMPLATE/`),系统会引导你填:

- 🐛 **Bug Report** — 复现步骤 + 环境信息 + 日志 + 严重度
- ✨ **Feature Request** — 用例 + 建议方案 + 替代方案 + 优先级 + 贡献意愿
- ❓ **Question** — 具体问题 + 上下文 + 话题分类
- 📚 **Documentation Issue** — 哪页 + 问题 + 建议修改(教程在 [agentcook-tutorial](https://github.com/agentcook-cc/agentcook-tutorial)/ 代码 ADR 在本仓 docs/adr/)
- 💬 **Discussion**(非 bug / 非 feature)— 直接去 [Discussions](https://github.com/agentcook-cc/agentcook/discussions),适合"我觉得 X / 怎么决定 Y / 我也做了类似的"

---

## 2. 提 PR 流程

### 小修(typo / link / 单文件 1-10 行)

直接 fork → 改 → PR / 我 24h 内 review + merge。

### 中改(bug fix / 文档完善 / 单 ADR refinement)

1. 先看是否有 ISSUE 在跟(避免重复)
2. fork → branch → 改 → PR(关联对应 issue)
3. 通过 CI(`make ci-local` 本地先跑)
4. 我 1 周内 review + merge

### 大改(新 feature / 架构变化 / 跨包改动)

1. **先开 [Discussion](https://github.com/agentcook-cc/agentcook/discussions) 聊**确认方向
2. 协调员 / 维护者 ack 方向后 → 起 ADR(`docs/adr/ADR-XXX-...md`)
3. ADR merge 后 → 实施 PR
4. 通过 CI + 至少 1 个维护者 approve
5. 我 2 周内 review + merge

---

## 3. 代码规范

### Python

- 用 `uv` 管理依赖 / 不用 pip 直装
- `make lint` 跑 ruff check + format check(必过)
- `make test-py-unit` 跑 unit 测试(必过 / CI gate)
- 测试金字塔 4 层(unit / integration / Pact contract / e2e)严格按 ADR-007
- 详 `agentcook-core/CONTRIBUTING.md`(若 sub-package 有更细规则)

### Java

- Java 17 + Spring Boot 3 + DDD 4 模块(api / application / domain / infrastructure)
- `./mvnw test` 必过(jacoco line ≥ 92% / branch ≥ 75%)
- 详 ADR-013 Java 业务后端 + `agentcook-java/docs/ddd-guide.md` 494 行

### 前端(双前端:Vue 3 admin + React 19 app)

- design-tokens 共享(详 ADR-003)
- ESLint v8 + vue-eslint-parser + @typescript-eslint/parser(Phase 6 #23 装入)
- `pnpm test` + `pnpm build` 必过
- Lighthouse Perf median ≥ 90(详 ADR-007 + B 视角)

### 通用风格

- 化名脱敏(详 [memory desensitization-redlines](https://github.com/agentcook-cc/agentcook-tutorial/blob/main/chapters/appendix/30-translate-internal-jargon.md)):0 真姓名 / 0 内部代号 / 0 真邮箱 / 0 真 IP / 0 真公司产品代号
- ADR 编号顺序(本仓 19 ADR 累计 / 新增按 ADR-020+ 顺延)
- commit message 含 `(scope)` + 简短描述 + 关键文件清单

---

## 4. 跨 repo 边界

agentcook 是 triple-repo 模式:

| 仓 | 范围 | 你 PR 该提到哪 |
|---|---|---|
| `agentcook-cc/agentcook`(本仓 / public)| 代码(Python 9 包 + Java DDD + 前端 + ADR + Workers + Helm)| 改代码 / ADR / docs |
| `agentcook-cc/agentcook-tutorial`(public)| 教程(30 讲 + 7 附录 + 旗舰博客 + 50 篇博客系列)| 改教程 / 报教程文档错(doc_issue.yml 选"教程仓")|
| `agentcook-cc/agentcook-workspace`(private)| 协作内部材料(progress / audit / brief)| **不接受外部 PR**(协调员内部 doc)|

跨 repo verify pre-push hook(详 `.githooks/pre-push`)— 防你 PR 代码到本仓后漏 commit 对应 progress 到 workspace 仓(cookbook 坑 22 教训累计 4+ 次)。

---

## 5. 维护者响应承诺

按 [Day 70 D0 应急 3 档](https://github.com/agentcook-cc/agentcook-tutorial/blob/main/faq/readers-faq.md#q40-github-issues-多久回):

- 🟢 **< 100 issue / 24h**:维护者(老A + 协调员)日内回 + 标 label
- 🟡 **100-500 issue / 24h**:全员投入 + 关键 bug Day 71 hotfix
- 🔴 **> 500 issue / 24h**:启动 Phase 5.5 稳定期 / 暂停新教程发布 / 全力修 bug + 更新 FAQ

**PR review SLA**:
- 小修 24h
- 中改 1 周
- 大改 2 周

---

## 6. 行为准则

- 互相尊重 / 反 over-confident / 反 ad-hominem
- 反向 fact-check 鼓励(我们的协作文化:Agent 揪我我感谢,你揪我我也感谢 — 详博客 [C5 reverse fact-check 文化怎么建立](https://github.com/agentcook-cc/agentcook-tutorial/blob/main/blog/series/C5-reverse-fact-check-culture.md))
- 黑话 / 阿里同款"赋能 / 抓手 / 对齐 / 拉通"等 不在本仓 issue / PR / discussion 出现

详 CODE_OF_CONDUCT.md(若加 / 当前 sufficient)。

---

## 7. License

本仓 [MIT License](./LICENSE)。

你的 PR 一旦 merge,内容归 agentcook contributors 共有 / MIT 协议持续生效。

如果你想 attribute 你的 PR / 名字加入 CONTRIBUTORS.md(若加 / Day 100+ 启动),merge PR 时告诉我即可。

---

## 8. 怎么联系

- GitHub Issues / Discussions(首选)
- 公众号"老A说" / 知乎"大厂码农老A" / 掘金 [大厂码农老A](https://juejin.cn/user/2147803289619047)
- 不接受 email 直接联系(避免 spam / 全在 GitHub 公开协作)

---

老A 说:**贡献不是 obligation,是协作的礼物**。哪怕一个 typo PR / 一个 issue 报错,都让这个项目更好。期待你来。

— 大厂码农老A,2026-06-13(Day 70 D0)
