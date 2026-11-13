import { test, expect } from "@playwright/test";

// Day 9 audit evidence — screenshots saved under test-results/.
// Run with:
//   PLAYWRIGHT_BASE_URL=http://localhost:9292 PLAYWRIGHT_AUDIT=1 \
//     pnpm playwright test e2e/audit-screenshot.spec.ts --project=smoke

test.skip(!process.env.PLAYWRIGHT_AUDIT, "audit-only spec; set PLAYWRIGHT_AUDIT=1");

const auditDir = "test-results/pact-broker";

test("pact-broker landing page", async ({ page }) => {
  // pact-broker has BASIC_AUTH; log in via URL credentials.
  const url = (process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:9292").replace("://", "://pact:pact@");
  const resp = await page.goto(url);
  expect(resp?.status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Pacts" })).toBeVisible();
  await expect(page.getByRole("grid")).toBeVisible();
  await page.screenshot({
    path: `${auditDir}/pact-broker-landing.png`,
    fullPage: true,
  });
});

test("pact-broker heartbeat endpoint", async ({ page }) => {
  const url = (process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:9292").replace("://", "://pact:pact@");
  const resp = await page.goto(`${url}/diagnostic/status/heartbeat`);
  expect(resp?.status()).toBe(200);
  await page.screenshot({
    path: `${auditDir}/pact-broker-heartbeat.png`,
    fullPage: true,
  });
});
