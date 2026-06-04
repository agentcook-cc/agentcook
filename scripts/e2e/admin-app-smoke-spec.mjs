/**
 * admin (Vue :5173) + app (React :5174) Playwright headless smoke 自动化
 *
 * 用途:
 *   1. 9 张截图覆盖完整用户旅程(admin 登录 / app 登录 / chat 输入 / 流式响应 /
 *      admin 仪表盘 / Plugin 菜单)
 *   2. 收集 console.error + pageerror 给 stress-test report 引证
 *   3. 验证 admin/app 真渲染了自定义 UI(不是 Vite 默认欢迎页)
 *
 * 谁用:
 *   - 部署闭环压测(参考 agentcook-workspace 内
 *     `tutorial/_internal/stress-test/deployment-loop-b-prompt.md`)
 *   - admin/app UI 回归测试(Day 75+ chat root cause 修后重跑 verify)
 *   - 50 周博客系列 D4 主题(Playwright e2e cross-browser 实战素材)
 *
 * 怎么跑:
 *   1. 后端 + 前端 dev server 都起来:`make dev` + `cd agentcook-admin && pnpm dev` +
 *      `cd agentcook-app && pnpm dev`
 *   2. `npx playwright install chromium`(首次需要)
 *   3. 默认截图落 `scripts/e2e/screenshots/`(已 .gitignore):
 *      `node scripts/e2e/admin-app-smoke-spec.mjs`
 *      或自定义截图目录:
 *      `SCREENSHOTS_DIR=/path/to/your/dir node scripts/e2e/admin-app-smoke-spec.mjs`
 *
 * 已知 limitation(2026-06-04 Day 70+ 实测):
 *   - chat 端到端要先 .env 注入 Qwen key + uv sync --all-packages --all-extras,
 *     否则 chat 会返 0 byte SSE(详 W3 ① A 修);默认 mock 模式截图只到 5174 渲染
 *   - admin /users/me 在 Day 70+ 修复前会死循环(详 W3 ① D 修);本脚本之后版本会跑通
 *
 * 演进轨迹:
 *   2026-06-04 Day 70+ Agent B 部署闭环压测产出(原名 deployment-loop-b-spec.mjs)
 *   2026-06-04 Day 70+ 协调员脱敏 + 迁移到 scripts/e2e/(env var fallback + 仓内截图目录)
 */

import { chromium } from "@playwright/test";
import fs from "fs";
import path from "path";

const SCREENSHOTS = process.env.SCREENSHOTS_DIR ||
  path.join(process.cwd(), "scripts/e2e/screenshots");

fs.mkdirSync(SCREENSHOTS, { recursive: true });
console.log(`[setup] SCREENSHOTS=${SCREENSHOTS}`);

async function main() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(`console.error: ${msg.text()}`);
  });

  // 1. admin login render
  await page.goto("http://localhost:5173", { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${SCREENSHOTS}/01-admin-login.png`, fullPage: true });
  const adminTitle = await page.title();
  const adminBodyText = await page.locator("body").innerText().catch(() => "");
  console.log(`[admin] title="${adminTitle}" / bodyLen=${adminBodyText.length}`);
  console.log(`[admin] body preview: ${adminBodyText.slice(0, 200).replace(/\n/g, " | ")}`);

  // 2. app render
  await page.goto("http://localhost:5174", { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${SCREENSHOTS}/02-app-login.png`, fullPage: true });
  const appTitle = await page.title();
  const appBodyText = await page.locator("body").innerText().catch(() => "");
  console.log(`[app] title="${appTitle}" / bodyLen=${appBodyText.length}`);
  console.log(`[app] body preview: ${appBodyText.slice(0, 200).replace(/\n/g, " | ")}`);

  // 3. app login form 走一遍
  await page.fill('input[placeholder*="username" i], input[name="username"], input[type="text"]', "alice").catch(() => {});
  await page.fill('input[type="password"]', "dev").catch(() => {});
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${SCREENSHOTS}/03-app-login-filled.png`, fullPage: true });
  const submitBtn = page.getByTestId("login-submit").or(page.getByRole("button", { name: /sign in/i }));
  const submitDisabled = await submitBtn.isDisabled().catch(() => null);
  console.log(`[app] submit disabled=${submitDisabled}`);
  await submitBtn.click({ timeout: 5000 }).catch((e) => console.log(`[app] click err: ${e.message}`));
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${SCREENSHOTS}/04-app-after-login.png`, fullPage: true });
  console.log(`[app] post-login url=${page.url()}`);

  // 4. 如果到了 chat 页, 发 1 次 chat
  if (page.url().includes("/chat") || page.url() === "http://localhost:5174/") {
    const textarea = page.locator('textarea[placeholder*="Type a message" i]');
    await textarea.waitFor({ timeout: 10000 }).catch(() => {});
    await textarea.fill("你好,用30字介绍自己").catch(() => {});
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${SCREENSHOTS}/05-app-chat-input.png`, fullPage: true });
    await page.getByRole("button", { name: /^send$/i }).click({ timeout: 5000 }).catch(() => {});
    // 等 streaming 内容
    await page.waitForTimeout(15000);
    await page.screenshot({ path: `${SCREENSHOTS}/06-app-chat-response.png`, fullPage: true });
    const messages = await page.locator('[role="article"], .message, [data-role="assistant"]').count().catch(() => 0);
    const allText = await page.locator("body").innerText();
    console.log(`[chat] messages_count=${messages} / has_streaming=${allText.includes("流式") || allText.length > 500}`);
    console.log(`[chat] body slice: ${allText.slice(allText.length - 800).replace(/\n/g, " | ")}`);
  }

  // 5. admin login + plugins
  await page.goto("http://localhost:5173/login", { waitUntil: "networkidle", timeout: 15000 });
  await page.waitForTimeout(1500);
  await page.fill('input[placeholder="Enter username"]', "alice").catch(() => {});
  await page.fill('input[placeholder="Enter password"]', "dev").catch(() => {});
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${SCREENSHOTS}/07-admin-login-filled.png`, fullPage: true });
  await page.getByTestId("login-submit").click({ timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${SCREENSHOTS}/08-admin-dashboard.png`, fullPage: true });
  console.log(`[admin] post-login url=${page.url()}`);
  // 找 Plugins 菜单
  await page.getByText(/plugin/i).first().click({ timeout: 5000 }).catch(() => {});
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${SCREENSHOTS}/09-admin-plugins.png`, fullPage: true });
  const pluginText = await page.locator("body").innerText();
  console.log(`[admin-plugins] has dingtalk=${pluginText.includes("dingtalk")} / has feishu=${pluginText.includes("feishu")} / has mcp=${pluginText.includes("mcp")}`);

  console.log(`\n[errors] ${errors.length} caught`);
  errors.slice(0, 20).forEach((e) => console.log(`  - ${e}`));

  await browser.close();
}

main().catch((e) => {
  console.error(`MAIN ERR: ${e.message}`);
  process.exit(1);
});
