/**
 * app ChatPage quota banner — ADR-018 cascade B Day 58.
 *
 * Mocks `/api/v1/quota` (Java backend) at the network layer so the spec
 * doesn't need a live Java instance. Asserts the banner flips between
 * "1 left" → "exhausted (downgraded)" as the mocked quota state changes.
 *
 * Why a mock instead of a true round-trip:
 *   - the banner contract is purely a UI affordance over the GET response
 *   - true quota burn requires a configured DASHSCOPE key + Java login
 *     issuing a real JWT, which Phase 5 backlog #11 (Turnstile) is also
 *     gated on. The mock keeps this test independent of those.
 *
 * Companion vitest covers `useQuota` logic itself; this spec is the
 * end-to-end render contract: data shape → DOM markers.
 */
import { test, expect } from "@playwright/test";

const SEED_ACCESS = "dev-token-e2e-quota";
const SEED_REFRESH = "dev-refresh-token-e2e-quota";
const JAVA_BASE = process.env.VITE_JAVA_API_BASE_URL ?? "http://localhost:8080";

test.describe("app ChatPage — ADR-018 quota banner", () => {
  test.beforeEach(async ({ page }) => {
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

  test("renders 'exhausted — downgraded' banner when used == quota", async ({
    page,
  }) => {
    await page.route(`${JAVA_BASE}/api/v1/quota`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          free_questions_used: 2,
          free_questions_quota: 2,
        }),
      });
    });

    await page.goto("/");
    await expect(page).not.toHaveURL(/\/login$/);

    const exhaustedBanner = page.getByTestId("quota-banner-exhausted");
    await expect(exhaustedBanner).toBeVisible();
    await expect(exhaustedBanner).toContainText("downgraded to glm-4-flash");
    await expect(exhaustedBanner).toContainText("(2/2)");
    await expect(page.getByTestId("quota-banner-warning")).toHaveCount(0);
  });
});
