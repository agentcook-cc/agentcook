import { test, expect } from "@playwright/test";

// Skip until B's admin/app dev server is up. To run locally:
//   pnpm --filter @agentcook-cc/admin dev   # in another terminal
//   PLAYWRIGHT_BASE_URL=http://localhost:5173 pnpm e2e
test.skip(
  !process.env.PLAYWRIGHT_BASE_URL && !process.env.CI,
  "set PLAYWRIGHT_BASE_URL to run e2e against a live server"
);

test("admin home renders", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/agentcook|admin/i);
});
