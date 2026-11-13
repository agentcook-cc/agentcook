/** Full stack: Java :8080 + runtime :8000 (required auth, mock provider, quota on) + app :5174. */
import { test, expect } from "@playwright/test";

test("register, use a tool, reload history, sign out and sign back in", async ({ page }) => {
  const username = `journey-${Date.now()}-${test.info().workerIndex}`;
  const password = "journey-password-123";
  await page.addInitScript(() => localStorage.setItem("agentcook_locale", "zh-CN"));
  await page.goto("/login");
  await expect(page.getByRole("link", { name: "先不登录，直接体验" })).toHaveCount(0);
  await page.getByRole("radio", { name: "注册" }).check();
  await page.getByLabel("用户名或邮箱").fill(username);
  await page.getByLabel("密码", { exact: true }).fill(password);
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/chat$/);

  const token = await page.evaluate(() => localStorage.getItem("access_token"));
  const headers = { Authorization: `Bearer ${token}` };
  const before = await page.request.get("/api/v1/quota", { headers });
  expect(before.status()).toBe(200);
  const initialQuota = await before.json();
  await page.getByRole("textbox").fill("calculate 2*21");
  await page.getByTestId("send-button").click();
  await expect(page.getByTestId("tool-call").first()).toHaveAttribute("data-status", "success");
  await expect(page.getByTestId("tool-call").first()).toHaveAttribute("data-tool", "calculator");
  await expect(page.getByTestId("assistant-message").last()).toHaveAttribute("data-status", "done");
  await expect(page.getByTestId("assistant-message").last()).toContainText("42");
  const conversationUrl = page.url();
  await expect
    .poll(async () => (await (await page.request.get("/api/v1/quota", { headers })).json()).used)
    .toBe(initialQuota.used + 1);
  await page.reload();
  await expect(page.getByTestId("assistant-message").last()).toContainText("42");
  await expect(page.getByTestId("session-list")).toContainText("calculate 2*21");

  await page.getByRole("button", { name: /退出|sign out/i }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(await page.evaluate(() => localStorage.getItem("access_token"))).toBeNull();
  expect(await page.evaluate(() => localStorage.getItem("refresh_token"))).toBeNull();
  await page.getByLabel("用户名或邮箱").fill(username);
  await page.getByLabel("密码", { exact: true }).fill("wrong-password");
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("auth-error")).toContainText("用户名或密码错误");
  await page.getByLabel("密码", { exact: true }).fill(password);
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/chat$/);
  await page.goto(conversationUrl);
  await expect(page.getByTestId("assistant-message").last()).toContainText("42");
});
