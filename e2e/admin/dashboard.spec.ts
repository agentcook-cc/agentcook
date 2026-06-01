/**
 * admin Dashboard — 4 stat cards render past loading.
 *
 * Phase 3 Day 27 — Agent C.
 *
 * Preconditions same as login.spec.ts. This test reuses the dev token
 * from a login round-trip rather than seeding localStorage directly,
 * because the auth store has key normalisation (camelCase from Java,
 * snake_case fallback) we don't want to drift away from here.
 *
 * What we assert:
 *   - URL settles on /dashboard
 *   - all four `.stat-number` slots leave the loading state (text is not
 *     the loading spinner ellipsis)
 *   - at least one card shows a parsed number (proves Promise.allSettled
 *     didn't fail-closed across all sources)
 *
 * We deliberately don't pin specific counts — the postgres-business DB
 * is empty in CI and only seeded ad-hoc locally.
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

test.describe("admin dashboard", () => {
  test("four stat cards render past loading", async ({ page }) => {
    await loginAsAlice(page);

    const statCards = page.locator(".stat-number");
    await expect(statCards).toHaveCount(4);

    // Each card eventually settles. The loading placeholder uses a
    // spinner/ellipsis (see DashboardView.vue:208) — assert each slot
    // ultimately renders something other than the placeholder.
    await expect
      .poll(
        async () => {
          const texts = await statCards.allTextContents();
          return texts.every((t) => t.trim().length > 0 && !/^[.…]+$/.test(t.trim()));
        },
        { timeout: 10_000 },
      )
      .toBe(true);

    // At least one card surfaces a parseable integer — proves the
    // Promise.allSettled pipeline didn't fail across every source.
    const texts = await statCards.allTextContents();
    const anyNumeric = texts.some((t) => /\d/.test(t));
    expect(anyNumeric, `no numeric stat in cards: ${JSON.stringify(texts)}`).toBe(true);
  });
});
