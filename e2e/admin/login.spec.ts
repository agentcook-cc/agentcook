/**
 * admin Login → Dashboard redirect.
 *
 * Phase 3 Day 27 — Agent C, first real e2e business spec (replaces the
 * mock-mode smoke from Day 26).
 *
 * Preconditions:
 *   - admin dev server on PLAYWRIGHT_BASE_URL (default http://localhost:5173)
 *   - Java backend on :8080 with `AuthController` (dev profile dummy token).
 *     `curl -X POST localhost:8080/api/v1/auth/login -d '{"username":"alice","password":"dev"}'`
 *     should return `{accessToken, tokenType, expiresIn}`.
 *
 * Local run:
 *   pnpm --filter @agentcook-cc/admin dev &
 *   PLAYWRIGHT_BASE_URL=http://localhost:5173 pnpm e2e e2e/admin/login.spec.ts
 *
 * Selectors lean on `autocomplete=username/current-password` (added by B
 * in LoginView.vue) rather than data-test attributes — those would be a
 * better long-term anchor; a Day 28+ ticket for B to add them.
 */

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

    await page.locator('input[autocomplete="username"]').fill("alice");
    await page.locator('input[autocomplete="current-password"]').fill("dev-secret");
    await page.getByRole("button", { name: /sign in/i }).click();

    // Spring Boot dev profile returns a dummy token for ANY non-empty
    // credentials, so redirect should happen unconditionally as long as
    // the network is reachable.
    await page.waitForURL(/\/dashboard$/, { timeout: 10_000 });
    await expect(page).toHaveURL(/\/dashboard$/);

    // Token persisted by the auth store.
    const token = await page.evaluate(() => {
      // The auth store writes via pinia-persistedstate or direct localStorage —
      // either way the token surfaces under one of these keys.
      return (
        localStorage.getItem("agentcook:auth:accessToken") ??
        localStorage.getItem("accessToken") ??
        ""
      );
    });
    expect(token).toMatch(/^dev-token-/);
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
