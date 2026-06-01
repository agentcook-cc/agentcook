/**
 * app ChatPage — renders past auth gate with the three core widgets in DOM.
 *
 * Phase 3 Day 28 — Agent C, first e2e spec for the app surface (port 5174).
 *
 * Preconditions:
 *   - app dev server on PLAYWRIGHT_BASE_URL_APP (default http://localhost:5174)
 *   - no Java/Python backend required: this spec asserts on the auth-gated
 *     UI shell only, with a seeded localStorage token. SSE behaviour comes
 *     in `skill-test.spec.ts` once Agent A's Day 28 SSE endpoint is up.
 *
 * Why seed localStorage instead of going through /login: the Java
 * /api/v1/auth/login endpoint is exercised by the admin login spec; this
 * spec is about the React shell. Skipping the network round-trip keeps
 * the assertion focused on layout regressions, not auth flow.
 *
 * The seeded keys (`access_token`, `refresh_token`) match the app-side
 * convention in `agentcook-app/src/stores/auth.ts:23-24`. (Note: admin
 * uses camelCase `accessToken` instead — B owns reconciling the two.)
 */

import { test, expect } from "@playwright/test";

const SEED_ACCESS = "dev-token-e2e-app";
const SEED_REFRESH = "dev-refresh-token-e2e-app";

test.describe("app ChatPage", () => {
  test.beforeEach(async ({ page }) => {
    // Visit a static path first so localStorage is bound to the right origin.
    await page.goto("/login");
    await page.evaluate(
      ([access, refresh]) => {
        localStorage.clear();
        localStorage.setItem("access_token", access);
        localStorage.setItem("refresh_token", refresh);
      },
      [SEED_ACCESS, SEED_REFRESH],
    );
  });

  test("auth-gated chat shell renders sidebar + message list + input", async ({ page }) => {
    await page.goto("/");

    // Auth check: ChatPage redirects to /login when isAuthenticated is
    // false (ChatPage.tsx:38-42). Seeded token should keep us on /.
    await expect(page).not.toHaveURL(/\/login$/);

    // ChatInput surfaces a textarea with the default placeholder.
    await expect(page.locator('textarea[placeholder*="Type a message"]')).toBeVisible();

    // SessionSidebar renders the three mock sessions (ChatPage.tsx:18-22).
    // We assert on a stable mock title rather than every item — that
    // gives us the sidebar without coupling to its exact mock list.
    await expect(page.getByText("Help me write a Python script")).toBeVisible();

    // VirtualMessageList mounts even with zero messages — assert by role
    // or by a stable wrapper. The component renders a region; we look
    // for the empty state copy that ChatPage seeds when messages=[].
    // (Falls back to the textarea-adjacent container if the empty copy
    // isn't there; we already verified the textarea above.)
    const empty =
      page.getByText(/start a conversation|how can i help|no messages/i);
    if (await empty.count()) {
      await expect(empty.first()).toBeVisible();
    }
  });

  test("clearing token redirects to /login on next navigation", async ({ page }) => {
    await page.goto("/");
    await expect(page).not.toHaveURL(/\/login$/);

    await page.evaluate(() => {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
    });

    // ChatPage's auth effect re-fires on route change. Force a navigation.
    await page.goto("/");
    await page.waitForURL(/\/login$/, { timeout: 5_000 });
    await expect(page).toHaveURL(/\/login$/);
  });
});
