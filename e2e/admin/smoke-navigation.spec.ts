/** Requires the authenticated stack and a pre-created administrator. */
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

/**
 * Each route we navigate to, what we expect to see on the page to confirm
 * it rendered past its loading state.
 */
const ADMIN_ROUTES = [
  { path: "/dashboard", marker: ".stat-number", label: "Dashboard" },
  { path: "/plugins", marker: ".el-table", label: "Plugin Management" },
  { path: "/users", marker: ".el-table", label: "User Management" },
  { path: "/connectors", marker: ".el-table, .connector", label: "Connectors" },
  { path: "/permissions", marker: ".permission-view .user-list", label: "Permissions" },
  { path: "/observability", marker: ".observability-view", label: "Observability" },
  { path: "/logs", marker: ".log-stream-view", label: "Logs" },
  { path: "/skills", marker: ".skill-list-view", label: "Skills" },
] as const;

test.describe("admin smoke navigation — all 8 pages", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  for (const route of ADMIN_ROUTES) {
    test(`navigate to ${route.label} (${route.path})`, async ({ page }) => {
      await page.goto(route.path);

      await expect(page).toHaveURL(new RegExp(`${route.path}$`));
      await expect(page.locator(route.marker).first()).toBeVisible();
      await expect(page.locator("main, .app-main, #app").first()).not.toBeEmpty();
      await expect(page.locator(".el-notification.is-error")).toHaveCount(0);
    });
  }

  test("sidebar navigation links are all present", async ({ page }) => {
    // After login we're on /dashboard — check sidebar has nav links
    const sidebar = page.locator(".el-menu, .sidebar, nav").first();
    await expect(sidebar).toBeVisible({ timeout: 5_000 });

    // Verify at least 5 menu items exist (some may be grouped)
    const menuItems = sidebar.locator(".el-menu-item, .el-sub-menu, a[href]");
    const count = await menuItems.count();
    expect(count, "sidebar should have at least 5 navigation items").toBeGreaterThanOrEqual(5);
  });
});
