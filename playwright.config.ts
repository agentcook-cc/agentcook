import { defineConfig, devices } from "@playwright/test";

/**
 * Day 28 (Agent C) — projects split by surface area.
 *
 * Two frontends run on different dev ports (admin :5173, app :5174), so a
 * single global `baseURL` no longer works once we have specs against
 * both. Each project below pins its own baseURL via env override (CI
 * runs them sequentially against the same job's services).
 *
 * Project layout:
 *   admin    → e2e/admin/**         baseURL = $PLAYWRIGHT_BASE_URL_ADMIN
 *   app      → e2e/app/**           baseURL = $PLAYWRIGHT_BASE_URL_APP
 *   smoke    → e2e/{smoke,audit}*   baseURL = $PLAYWRIGHT_BASE_URL (generic)
 *
 * The legacy `PLAYWRIGHT_BASE_URL` still drives the smoke project so the
 * Day 26 mock-mode CI workflow keeps working without changes.
 *
 * All projects pin Chromium — cross-browser sweeps happen via a
 * separate matrix in CI when we need them, not on every push. Faster
 * baseline + matches the Day 26 `--with-deps chromium` install.
 */

const ADMIN_BASE = process.env.PLAYWRIGHT_BASE_URL_ADMIN ?? "http://localhost:5173";
const APP_BASE = process.env.PLAYWRIGHT_BASE_URL_APP ?? "http://localhost:5174";
const SMOKE_BASE =
  process.env.PLAYWRIGHT_BASE_URL ?? process.env.PLAYWRIGHT_BASE_URL_ADMIN ?? "http://localhost:5173";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "github" : "html",
  use: {
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "admin",
      testDir: "./e2e/admin",
      use: { ...devices["Desktop Chrome"], baseURL: ADMIN_BASE },
    },
    {
      name: "app",
      testDir: "./e2e/app",
      use: { ...devices["Desktop Chrome"], baseURL: APP_BASE },
    },
    {
      // Generic smoke + audit-screenshot specs that predate the split.
      // Match by filename so they don't get double-run by admin/app.
      name: "smoke",
      testMatch: ["smoke.spec.ts", "audit-screenshot.spec.ts"],
      use: { ...devices["Desktop Chrome"], baseURL: SMOKE_BASE },
    },
  ],
});
