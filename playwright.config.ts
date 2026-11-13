import { defineConfig, devices } from "@playwright/test";

/** Anonymous and authenticated stacks run on separate app/runtime ports.
 * See e2e/README.md for commands; no scenario silently changes the auth mode.
 */
const ADMIN_BASE = process.env.PLAYWRIGHT_BASE_URL_ADMIN ?? "http://localhost:5173";
const APP_BASE = process.env.PLAYWRIGHT_BASE_URL_APP ?? "http://localhost:5174";
const SMOKE_BASE = process.env.PLAYWRIGHT_BASE_URL ?? process.env.PLAYWRIGHT_BASE_URL_ADMIN ?? "http://localhost:5173";

const ANONYMOUS_BASE =
  process.env.PLAYWRIGHT_BASE_URL_ANONYMOUS ?? process.env.PLAYWRIGHT_BASE_URL_APP ?? "http://localhost:5175";

const APP_CROSS_BROWSER = process.env.PLAYWRIGHT_APP_CROSS_BROWSER === "1";

const appProjects = APP_CROSS_BROWSER
  ? [
      {
        name: "app-chromium",
        testDir: "./e2e/app",
        testIgnore: "full-user-journey.spec.ts",
        use: { ...devices["Desktop Chrome"], baseURL: ANONYMOUS_BASE },
      },
      {
        name: "app-firefox",
        testDir: "./e2e/app",
        testIgnore: "full-user-journey.spec.ts",
        use: { ...devices["Desktop Firefox"], baseURL: ANONYMOUS_BASE },
      },
      {
        name: "app-webkit",
        testDir: "./e2e/app",
        testIgnore: "full-user-journey.spec.ts",
        use: { ...devices["Desktop Safari"], baseURL: ANONYMOUS_BASE },
      },
    ]
  : [
      {
        name: "app",
        testDir: "./e2e/app",
        testIgnore: "full-user-journey.spec.ts",
        use: { ...devices["Desktop Chrome"], baseURL: ANONYMOUS_BASE },
      },
    ];

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
    // Use a pre-installed Chromium (e.g. a container image whose browser
    // build doesn't match this Playwright version) instead of downloading.
    ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } }
      : {}),
  },
  projects: [
    {
      name: "admin",
      testDir: "./e2e/admin",
      use: { ...devices["Desktop Chrome"], baseURL: ADMIN_BASE },
    },
    ...appProjects,
    {
      name: "app-full-stack",
      testDir: "./e2e/app",
      testMatch: "full-user-journey.spec.ts",
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
