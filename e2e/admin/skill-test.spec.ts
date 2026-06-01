/**
 * admin SkillTestDialog — mock SSE chunks stream into the output box.
 *
 * Phase 3 Day 29 — Agent C (Day 28 carried over per brief flag).
 *
 * Why mock SSE rather than hit real Python:
 *   - The skill-test surface fan-outs across three runtimes (admin :5173 ←
 *     fetch ← Python :8000 ← `_mock_skill_stream` 10×500ms chunks). Pulling
 *     all three up in CI works but adds 30-60s to the e2e job and ties this
 *     spec's reliability to Python liveness.
 *   - The bug class we want to catch is in `useSseStream` parsing & DOM
 *     update flow inside SkillTestDialog.vue, not in the Python emitter.
 *     A controlled mock stream lets us assert on chunk count + final
 *     accumulated text deterministically.
 *
 * The integration-flavoured "real Python SSE" spec belongs in a separate
 * suite once Python is added to the e2e job (tracked as a Day 30+ task
 * if/when we want true e2e SSE).
 *
 * Wire format reference: `agentcook/src/agentcook_app/routers/skills.py`
 * uses `data: {json}\n\n` per the SSE default `data` event.
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

test.describe("admin SkillTestDialog SSE", () => {
  test("five SSE chunks accumulate in the output box", async ({ page, context }) => {
    // Stub the Python SSE endpoint before the dialog fires its fetch.
    // The `**` glob covers both http://localhost:8000 and the in-CI host.
    await context.route("**/api/v1/skills/*/test/stream", async (route) => {
      const lines = [
        'data: {"chunk":"hello","index":0}\n\n',
        'data: {"chunk":" world","index":1}\n\n',
        'data: {"chunk":". this","index":2}\n\n',
        'data: {"chunk":" is","index":3}\n\n',
        'data: {"chunk":" mocked","index":4,"finish":true}\n\n',
      ];
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

    await loginAsAlice(page);
    await page.goto("/skills");

    // Wait for at least one card; SkillListView seeds five mock skills.
    const firstTestBtn = page.getByRole("button", { name: /^test$/i }).first();
    await expect(firstTestBtn).toBeVisible({ timeout: 10_000 });
    await firstTestBtn.click();

    // Dialog mounts. Input is required by the form's pre-flight validator
    // (SkillTestDialog.vue:131 — "Input is required ...").
    const input = page.getByPlaceholder(/skilltest|leave blank|input|message/i).first();
    // Fall back to first textarea inside the dialog if placeholder text shifted.
    const textarea = (await input.count())
      ? input
      : page.locator('.el-dialog textarea').first();
    await textarea.fill("hello from playwright");

    await page.getByRole("button", { name: /^run$/i }).click();

    // The output `<pre>` accumulates chunk text; useSseStream concatenates
    // each `data:` json's `chunk` field. Assert the final concat appears.
    await expect(
      page.locator(".el-dialog .output-box pre"),
    ).toContainText("hello world. this is mocked", { timeout: 10_000 });

    // The "done" tag carries the chunk count; useSseStream emits it once
    // the response body closes.
    await expect(page.locator(".el-dialog .el-tag")).toContainText(/done|chunks/i, {
      timeout: 10_000,
    });
  });
});
