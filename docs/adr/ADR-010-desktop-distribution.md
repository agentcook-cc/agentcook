# ADR-010: 桌面端打包与分发(零成本开发者预览路线)

## Status

Accepted (2026-05-16,**2026-05-17 修订**)

> **修订说明**:v1 原决策走"商业级范本"路径(Apple Developer + Windows EV + 完整自动更新链路,年成本 $500)。v2 修订为"零成本开发者预览"路线 — 与 agentcook 实际定位(开源 + 开发者优先 + 教程配套)对齐,前期不投入分发成本,保留升级触发路径。

## Context

Phase 1 起 `agentcook-app` 提供 Web + **Electron 桌面端**两种发布形态。ADR-006(Blue-Green)仅覆盖 Web 服务,桌面端需独立决策:打包、签名、分发、更新。

**关键定位前提**(决定本 ADR 走向):
- agentcook 是**开源教程配套工程**,主受众是开发者(教程读者 / GitHub Star 用户 / 求职作品集观众)
- 这群人**完全能接受 unsigned 应用**(他们装 VSCode / Postman / Docker / Cursor 等都习惯了"右键打开"或 SmartScreen 警告)
- 教程一篇一篇在掘金 / 公众号 / GitHub 发布,桌面端只是**让读者能下载试用**,不是"普通用户双击即用"的商业产品

**桌面端面临的特殊问题**(若走商业级路径):
- macOS Gatekeeper 拦截未签名应用
- Windows SmartScreen 警告
- 用户对二进制的信任(供应链投毒)
- 修复 lead time(无自动更新 → 几周到几个月)

但这些问题对**开发者用户群体**是可接受的成本 — 没必要前期就投入年费换商业级体验。

## Decision

### v2 当前决策:零成本开发者预览(Phase 1-4)

#### 三平台打包矩阵

| 平台 | 打包格式 | 签名 | 用户首次启动体验 | 自动更新 |
|---|---|---|---|---|
| **macOS** | `.zip`(含 `.app`,**不用 .dmg** 避免装载步骤) | ❌ 无 | 右键 → "打开"(README + GIF 教学) | ⚠️ 不支持真自动更新 — app 内"检查更新"按钮跳转 GitHub Releases |
| **Windows** | `.exe` portable(免装)+ NSIS installer | ❌ 无 | SmartScreen "未知发布者"警告 → 点"更多信息"→ 仍要运行 | ⚠️ 同上 |
| **Linux** | AppImage(主推)+ DEB(可选) | ❌ 无 | `chmod +x && ./xxx.AppImage` 一行 | ✅ AppImage 内置 update 机制,不依赖签名 |

#### 关键 trade-off:macOS / Windows 没有真自动更新

`electron-updater` 在 macOS 上用 Squirrel.Mac,**要求应用签名**才能跑,unsigned 会静默失败。Windows NSIS 理论上能不签名更新,但用户每次更新仍会看到 SmartScreen 警告。

**应对方案**:
- app 启动时调用 GitHub Releases API 检查最新版
- 有新版 → 在 app 内显示通知 + "查看更新"按钮
- 按钮跳转浏览器到 GitHub Release 页面 → 用户手动下载
- Linux 用户走 AppImage 内置更新(完整体验)

这个限制对开发者用户**完全可接受**(他们更新 VSCode / Cursor 也是这个模式或类似)。

#### 通道(canary / beta / stable)

仍 3 channel,**全部 unsigned**,通过 GitHub Releases 分发:

| Channel | 节奏 | GitHub Release 标记 |
|---|---|---|
| canary | 每日 nightly,带 commit hash | `prerelease: true` + tag `vX.Y.Z-canary.YYYYMMDD` |
| beta | 每周,经基础冒烟测试 | `prerelease: true` + tag `vX.Y.Z-beta.N` |
| stable | 每月,经完整 QA | `prerelease: false` + tag `vX.Y.Z` |

GitHub Releases 选型理由:**零成本** + 开发者群体熟悉 + 自带下载统计 + 与代码仓库一体(免外部托管)。

#### README 教学(关键交付,Phase 3 Agent B 写)

`agentcook-app/README.md` 必须包含:
- macOS 章节:截图 + GIF 演示"右键 → 打开"全流程
- Windows 章节:截图演示"更多信息 → 仍要运行"
- Linux 章节:`chmod +x` 一行命令
- "为什么没签名?" 段落:坦白说明这是开源开发者预览版,商业级签名是 v2 升级路径

教学缺失 = 用户骂街风险。这是本 ADR 的**最重要交付物**。

### v1 升级路径:何时考虑投入分发成本

以下任一信号触发**重新评估**(并不强制升级):

| 信号 | 触发动作 | 一次性成本 |
|---|---|---|
| 非开发者用户反馈 ≥ 30%(教程读者中大量"装不上"求助) | 申请 Apple Developer Program | $99/年 |
| Stable channel 真实 DAU ≥ 1000 | 评估 Apple Developer | $99/年 |
| 启动 enterprise 版本(若有) | **必须**申请 Apple Developer + Windows EV | $99 + $300-500/年 |
| 准备上 Mac App Store(争取流量入口) | **必须**申请 Apple Developer | $99/年 + 30% 抽成 |
| Apple 政策变化:强制 .app 公证才能运行 | 紧急申请 + 重新打包链路 | $99/年 |

**升级时切换路径**(预留好,不要现在做):
- 申请 Apple Developer → 配置 electron-builder 的 mac.identity + notarize
- 切换 macOS 打包为 .dmg + 签名 + 公证
- 启用 `electron-updater` 真自动更新
- 重新打 stable channel 通知用户"已转商业级签名版"

## Consequences

### Positive
- ✅ **零年费成本**,符合开源项目"低门槛起步"原则,**省 $500/年**
- ✅ 开发者用户接受度高(目标受众的使用习惯匹配)
- ✅ Linux 用户体验完美(AppImage 不依赖签名是事实标准)
- ✅ GitHub Releases 免费 + 自带下载统计 + 与代码仓库一体
- ✅ **保留完整升级路径**(任何信号触发后可补 Apple Developer / EV)
- ✅ 减少 Phase 1-4 摩擦(无需在 Phase 2 前操心 Apple 账号审核)

### Negative
- ⚠️ macOS 用户:首次启动必须右键 → 打开(教学截图缓解)
- ⚠️ macOS 用户:**无真自动更新** — 只能 in-app 检测 + 跳转手动下载
- ⚠️ Windows 用户:SmartScreen 警告(用户需点"更多信息")
- ⚠️ 非开发者用户群体扩展受限(预期内,目标用户就是开发者)
- ⚠️ 部分 macOS 系统 API(摄像头/麦克风/通知/keychain)在 unsigned 下可能受限 → ADR-011 等模块设计时避开重度依赖

### Risk
- ❗ macOS Catalina+ 的 Gatekeeper 比之前严,部分用户右键打开仍可能报错 → 教学必须详细 + 准备 FAQ
- ❗ Windows 11 SmartScreen 越来越严,某些边缘版本可能直接拒绝 → 监控用户反馈
- ❗ Apple 政策变化:若强制所有 .app 必须公证(目前仍只是警告)→ 需紧急升级到 v1 商业级路径
- ❗ GitHub Releases 单文件 2GB 限制:Electron 安装包通常 80-200MB,远低于限制 → 当前无风险

## Alternatives Considered

| 方案 | 处理 | 否决/暂搁置理由 |
|---|---|---|
| ✅ **B. 零成本开发者预览**(当前 v2) | 选 | 与定位匹配,留升级路径,省 $500/年 |
| ⏸ C. 商业级 Apple Developer + 完整自动更新 | **暂搁置,作为升级路径** | 与开源 + 开发者优先定位错位;v1-v4 阶段不需要;升级触发条件已写入 |
| ❌ A. 纯 Web 不做桌面 | 否决 | 失去差异化卖点 + 教程"如何做 Electron 桌面 Agent"章节素材没有 |
| ❌ Tauri 替代 Electron | 暂不考虑 | 团队 React 栈成熟度高,Tauri 学习曲线 + 生态不及。v2 可重评 |
| ❌ 临时 ad-hoc 签名(`codesign --sign -`) | 否决 | 只能本机,无法分发 |
| ❌ 自签名 CA 证书让用户信任 | 否决 | 用户操作复杂度比 unsigned 还高,无意义 |

## Implementation

### Phase 1 (Day 6-15)
- 仅 ADR 收敛,**不动代码**,不申请任何账号

### Phase 3 (Day 26-37)
- **Agent B**:Electron 端打包配置(unsigned 路径)
- **Agent B**:`agentcook-app/README.md` 三平台首次启动教学(截图 + GIF + FAQ + "为什么没签名?"说明)
- **Agent C**:`.github/workflows/release-desktop.yml`(unsigned 三平台 build → GitHub Releases 上传)

### Phase 4 (Day 38-47)
- **Agent C**:in-app "检查更新" 按钮 + GitHub Releases API 集成 + 新版通知 UI
- **Agent C**:AppImage 自动更新链路(Linux 完整体验)
- **Agent C**:3 channel(canary/beta/stable)用 GitHub prerelease 标志区分

### Phase 5 / 上线后
- 收集真实用户反馈,**按升级触发条件评估**是否要补 Apple Developer

## References

- electron-builder docs: https://www.electron.build/
- AppImage update spec: https://github.com/AppImage/AppImageSpec/blob/master/draft.md
- GitHub Releases API: https://docs.github.com/en/rest/releases
- macOS Gatekeeper 用户教学最佳实践: 参考 OBS Studio / Audacity / Krita 等开源 macOS 应用 README
