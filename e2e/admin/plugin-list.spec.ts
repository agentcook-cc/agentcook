/**
 * admin PluginListView — page loads against the real Java endpoint.
 *
 * Phase 3 Day 27 — Agent C.
 *
 * Preconditions:
 *   - admin dev server + Java backend up (see login.spec.ts header)
 *   - Java DB may or may not have plugins seeded; this spec does NOT
 *     assert on rows. B's Day 27 PluginCreateDialog will exercise the
 *     non-empty path; today we just prove the page renders and the
 *     real-client call doesn't throw 401 / 5xx.
 *
 * Why this matters: the page was switched from mock to `javaClient.get`
 * on Day 24 (see PluginListView.vue diff). A 401/CORS regression here
 * would silently revert that progress; this spec catches it.
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

test.describe("admin plugin list", () => {
  test("renders page heading and table (rows allowed to be empty)", async ({ page }) => {
    await loginAsAlice(page);

    // Hook into Network so we can assert the real Java call landed —
    // not just that an empty table was rendered from a CORS rejection.
    const pluginsRequest = page.waitForResponse(
      (r) => r.url().includes("/api/v1/plugins") && r.request().method() === "GET",
      { timeout: 10_000 },
    );

    await page.goto("/plugins");
    const resp = await pluginsRequest;
    expect([200, 204]).toContain(resp.status());

    await expect(page.getByRole("heading", { name: /plugin management/i })).toBeVisible();

    // El-Table renders even on empty data — at least the table shell
    // is in the DOM. We don't assert on row count: postgres-business
    // is empty in CI and only seeded ad-hoc.
    await expect(page.locator(".el-table")).toBeVisible();

    // No unhandled error banner. ElNotification surfaces under a fixed
    // class; absence proves the request succeeded end-to-end.
    await expect(page.locator(".el-notification.is-error")).toHaveCount(0);
  });
});
