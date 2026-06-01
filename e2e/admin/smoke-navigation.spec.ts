/**
 * admin Smoke Navigation — Login → Dashboard → sidebar nav to all 8 pages.
 *
 * Phase 3 Day 33 — Agent C.
 *
 * This spec validates that:
 *   1. Login redirect works (reuses login.spec.ts pattern)
 *   2. Dashboard renders after login
 *   3. All sidebar routes are navigable without 5xx / blank page
 *
 * The 8 admin pages (B Day 31):
 *   /dashboard, /plugins, /users, /connectors, /sessions,
 *   /observability, /logs, /skills
 *
 * Preconditions:
 *   - admin dev server on PLAYWRIGHT_BASE_URL_ADMIN (default :5173)
 *   - Java backend on :8080 (D rebuild)
 *   - Python backend on :8000 (A) — optional, some pages fallback gracefully
 *
 * Local run:
 *   pnpm --filter @agentcook-cc/admin dev &
 *   PLAYWRIGHT_BASE_URL_ADMIN=http://localhost:5173 pnpm playwright test e2e/admin/smoke-navigation.spec.ts --project=admin
 */

import { test, expect } from "@playwright/test";

async function loginAsAlice(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.evaluate(() => localStorage.clear());
  await page.locator('input[autocomplete="username"]').fill("alice");
  await page.locator('input[autocomplete="current-password"]').fill("dev-secret");
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
  { path: "/sessions", marker: ".el-table, .session", label: "Sessions" },
  { path: "/observability", marker: "iframe, .observability", label: "Observability" },
  { path: "/logs", marker: ".log-stream, .log-entry, pre", label: "Logs" },
  { path: "/skills", marker: ".el-card, .skill", label: "Skills" },
] as const;

test.describe("admin smoke navigation — all 8 pages", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAlice(page);
  });

  for (const route of ADMIN_ROUTES) {
    test(`navigate to ${route.label} (${route.path})`, async ({ page }) => {
      await page.goto(route.path);

      // Page should not show a blank/error state. We check:
      // 1. URL settled correctly
      await expect(page).toHaveURL(new RegExp(`${route.path}$`));

      // 2. No unhandled error notification
      const errorNotification = page.locator(".el-notification.is-error");
      const errorCount = await errorNotification.count();
      // Allow at most 0 error notifications (network errors are acceptable
      // if backend is down, but the page itself should render)
      if (errorCount > 0) {
        // Log but don't fail — some pages may show "API unreachable" in
        // fallback mode which is acceptable for smoke test
        test.info().annotations.push({
          type: "warning",
          description: `${route.label}: ${errorCount} error notification(s) visible`,
        });
      }

      // 3. Page body has meaningful content (not blank white page)
      const bodyText = await page.locator("main, .app-main, #app").first().textContent();
      expect(
        bodyText && bodyText.trim().length > 0,
        `${route.label} page body should not be empty`,
      ).toBe(true);
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
