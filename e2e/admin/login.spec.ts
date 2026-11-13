/** Requires Java dev profile with admin configured and the authenticated runtime. */
import { test, expect } from "@playwright/test";

test.describe("admin login flow", () => {
  test.beforeEach(async ({ page }) => {
    // Each test starts logged-out — defensive, since dev server persists
    // localStorage across browser contexts in some pnpm dev setups.
    await page.goto("/login");
    await page.evaluate(() => localStorage.clear());
  });

  test("happy path: dev credentials redirect to /dashboard", async ({ page }) => {
    await page.goto("/login");

    await expect(page).toHaveURL(/\/login$/);

    await page.locator('input[autocomplete="username"]').fill("admin");
    await page
      .locator('input[autocomplete="current-password"]')
      .fill(process.env.E2E_ADMIN_PASSWORD ?? "admin-password-123");
    await page.getByRole("button", { name: /sign in/i }).click();

    await page.waitForURL(/\/dashboard$/, { timeout: 10_000 });
    await expect(page).toHaveURL(/\/dashboard$/);

    // Token persisted by the auth store.
    const token = await page.evaluate(() => localStorage.getItem("access_token"));
    expect(token).toBeTruthy();
    const payload = JSON.parse(Buffer.from(token!.split(".")[1], "base64url").toString());
    expect(payload.roles).toContain("admin");
  });

  test("empty credentials show inline validation, no redirect", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: /sign in/i }).click();
    // LoginView.vue surfaces "Please enter username and password" via
    // its el-alert error region.
    await expect(page.getByText(/please enter username and password/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });
});

test("ordinary user cannot enter the console", async ({ page, request }) => {
  const username = `ordinary-${Date.now()}`;
  const password = "ordinary-password-123";
  const response = await request.post("http://127.0.0.1:8080/api/v1/auth/register", { data: { username, password } });
  expect(response.status()).toBe(201);
  await page.goto("/login");
  await page.locator('input[autocomplete="username"]').fill(username);
  await page.locator('input[autocomplete="current-password"]').fill(password);
  await page.getByTestId("login-submit").click();
  await expect(page.getByText("该账号没有管理员权限")).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("access_token"))).toBeNull();
  await page.goto("/users");
  await expect(page).toHaveURL(/\/login/);
});
