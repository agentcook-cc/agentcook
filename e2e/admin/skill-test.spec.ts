/** Requires Java dev profile with admin configured and the authenticated runtime. */
/** Skill execution SSE is stubbed with the runtime wire format. */
import { test, expect } from "@playwright/test";

async function loginAsAdmin(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.evaluate(() => localStorage.clear());
  await page.locator('input[autocomplete="username"]').fill("admin");
  await page
    .locator('input[autocomplete="current-password"]')
    .fill(process.env.E2E_ADMIN_PASSWORD ?? "admin-password-123");
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL(/\/dashboard$/, { timeout: 10_000 });
}

test.describe("admin SkillTestDialog SSE", () => {
  test("five SSE chunks accumulate in the output box", async ({ page, context }) => {
    // Stub the Python SSE endpoint before the dialog fires its fetch.
    // The `**` glob covers both http://localhost:8000 and the in-CI host.
    await context.route("**/api/v1/skills/*/test/stream", async (route) => {
      expect(route.request().postDataJSON()).toEqual({ input: "hello from playwright" });
      const lines = ["hello", " world", ". this", " is", " mocked"].map(
        (delta, chunk_index) =>
          `data: ${JSON.stringify({ type: "delta", delta, chunk_index, total: null, finished: false })}\n\n`,
      );
      lines.push('data: {"type":"done","delta":"","chunk_index":5,"total":null,"finished":true}\n\n');
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        headers: {
          "cache-control": "no-cache",
          "x-accel-buffering": "no",
        },
        body: lines.join(""),
      });
    });

    await loginAsAdmin(page);
    await page.goto("/skills");

    const firstTestBtn = page.getByRole("button", { name: /^test$/i }).first();
    await expect(firstTestBtn).toBeVisible({ timeout: 10_000 });
    await firstTestBtn.click();

    await page.locator(".el-dialog textarea").first().fill("hello from playwright");

    await page.getByRole("button", { name: /^run$/i }).click();

    // The output `<pre>` accumulates chunk text; useSseStream concatenates
    // each `data:` frame's `delta` field. Assert the final concat appears.
    await expect(page.locator(".el-dialog .output-box pre")).toContainText("hello world. this is mocked", {
      timeout: 10_000,
    });

    await expect(page.getByRole("dialog").getByText("done · 5 chunks", { exact: true })).toBeVisible();
  });
});
