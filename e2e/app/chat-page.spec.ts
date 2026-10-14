/**
 * app ChatPage shell + auth gating.
 *
 * The chat page follows the runtime's auth mode (GET /api/v1/runtime):
 * - `optional` / `disabled` (local dev default): usable without signing in;
 * - `required` (production): unauthenticated visitors go to /login.
 *
 * Requires the Python runtime behind the Vite proxy (see agent-chat.spec.ts).
 */
import { test, expect } from "@playwright/test";

test.describe("app ChatPage", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.evaluate(() => localStorage.clear());
  });

  test("renders sidebar, empty state and input without signing in (optional auth)", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/chat$/);
    await expect(page.getByRole("textbox")).toBeVisible();
    await expect(page.getByTestId("session-list")).toBeVisible();
    await expect(page.getByTestId("empty-state")).toBeVisible();
    await expect(page.getByTestId("agent-picker")).toBeVisible();
    await expect(page.getByRole("button", { name: /sign in|登录/i })).toBeVisible();
  });

  test("redirects to /login when the runtime requires auth", async ({ page }) => {
    await page.route("**/api/v1/runtime", async (route) => {
      const response = await route.fetch();
      const body = await response.json();
      await route.fulfill({ response, json: { ...body, auth_mode: "required" } });
    });
    await page.goto("/chat");
    await page.waitForURL(/\/login$/, { timeout: 5_000 });
  });

  test("shows a clear error when the runtime is unreachable", async ({ page }) => {
    await page.route("**/api/v1/runtime", (route) => route.fulfill({ status: 502, body: "bad gateway" }));
    await page.goto("/chat");
    await expect(page.getByRole("alert")).toContainText(/runtime|运行时/i, { timeout: 10_000 });
  });
});
