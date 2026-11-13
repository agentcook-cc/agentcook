/** Requires the authenticated stack and a configured admin account. */
import { test, expect } from "@playwright/test";

async function loginAsAdmin(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.evaluate(() => localStorage.clear());
  await page.locator('input[autocomplete="username"]').fill("admin");
  await page
    .locator('input[autocomplete="current-password"]')
    .fill(process.env.E2E_ADMIN_PASSWORD ?? "admin-password-123");
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL(/\/dashboard$/, { timeout: 10_000 });
}

test.describe("admin user CRUD", () => {
  test("user list page renders table with no errors", async ({ page }) => {
    await loginAsAdmin(page);

    const usersRequest = page.waitForResponse(
      (r) => r.url().includes("/api/v1/users") && r.request().method() === "GET",
      { timeout: 10_000 },
    );

    await page.goto("/users");
    const resp = await usersRequest;
    expect([200, 204]).toContain(resp.status());

    await expect(page.locator(".el-table")).toBeVisible();
    await expect(page.locator(".el-notification.is-error")).toHaveCount(0);
  });

  test("suspend and reactivate a real user, preserving status after reload", async ({ page, request }) => {
    const username = `managed-${Date.now()}`;
    const password = "managed-password-123";
    const registered = await request.post("http://127.0.0.1:8080/api/v1/auth/register", {
      data: { username, password },
    });
    expect(registered.status()).toBe(201);
    await loginAsAdmin(page);
    await page.goto("/users");
    await page.getByPlaceholder("Search by email or nickname...").fill(username);
    const row = page.locator(".el-table__row").filter({ hasText: username });
    await expect(row).toContainText("ACTIVE");
    await row.getByRole("button", { name: "Suspend", exact: true }).click();
    const suspended = page.waitForResponse((r) => r.url().endsWith("/suspend") && r.request().method() === "PUT");
    await page.getByRole("button", { name: "OK", exact: true }).click();
    expect((await suspended).status()).toBe(200);
    await expect(row).toContainText("SUSPENDED");
    const blocked = await request.post("http://127.0.0.1:8080/api/v1/auth/login", { data: { username, password } });
    expect(blocked.status()).toBe(403);
    await page.reload();
    await page.getByPlaceholder("Search by email or nickname...").fill(username);
    await expect(row).toContainText("SUSPENDED");
    await row.getByRole("button", { name: "Activate", exact: true }).click();
    const activated = page.waitForResponse((r) => r.url().endsWith("/activate") && r.request().method() === "PUT");
    await page.getByRole("button", { name: "OK", exact: true }).click();
    expect((await activated).status()).toBe(200);
    await expect(row).toContainText("ACTIVE");
    const login = await request.post("http://127.0.0.1:8080/api/v1/auth/login", { data: { username, password } });
    expect(login.status()).toBe(200);
  });
});
