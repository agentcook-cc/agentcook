/**
 * Agent chat, end to end: React app (Vite :5174) → proxy → Python runtime
 * (:8000) running the offline mock model. No Java needed — the runtime
 * defaults to AGENTCOOK_AUTH_MODE=optional, so the app works anonymously.
 *
 * Start the stack:
 *   AGENTCOOK_MOCK_DELAY_MS=20 uv run uvicorn agentcook_app.main:app --port 8000
 *   pnpm --filter @agentcook-cc/app dev
 *
 * The mock model is deterministic, so assertions can be exact: the
 * calculator really runs, delegation really happens, transcripts really
 * persist.
 */
import { expect, test, type Page } from "@playwright/test";

async function send(page: Page, text: string) {
  const input = page.getByRole("textbox");
  await input.fill(text);
  await input.press("Enter");
}

test.describe("agent chat", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.evaluate(() => localStorage.clear());
  });

  test("empty state, tool call, answer, persistence", async ({ page }) => {
    await page.goto("/chat");
    await expect(page.getByTestId("empty-state")).toBeVisible();
    await expect(page.getByTestId("mock-badge")).toBeVisible();

    await send(page, "calculate 1299 * 0.85 - 50");

    const tool = page.getByTestId("tool-call").first();
    await expect(tool).toHaveAttribute("data-tool", "calculator");
    await expect(tool).toHaveAttribute("data-status", "success", { timeout: 15_000 });
    const reply = page.getByTestId("assistant-message").last();
    await expect(reply).toHaveAttribute("data-status", "done", { timeout: 15_000 });
    await expect(reply).toContainText("1054.15");
    await expect(page.getByTestId("run-footer").last()).toContainText("mock-agent");

    // The conversation got an id, shows in the sidebar and survives reload.
    await expect(page).toHaveURL(/\/chat\/c-/);
    await expect(page.getByTestId("session-list")).toContainText("calculate 1299 * 0.85 - 50");
    await page.reload();
    await expect(page.getByTestId("assistant-message").last()).toContainText("1054.15");
    await expect(page.getByTestId("tool-call").first()).toHaveAttribute("data-status", "success");

    // Tool card expands to show input + output.
    await page.getByTestId("tool-call").first().getByRole("button").click();
    await expect(page.getByTestId("tool-call").first()).toContainText('"expression"');
  });

  test("delegation to a specialist agent is visible", async ({ page }) => {
    await page.goto("/chat");
    await send(page, "please ask the analyst to review our sales");
    const card = page.locator('[data-testid="tool-call"][data-tool="delegate_to_analyst"]');
    await expect(card).toHaveAttribute("data-status", "success", { timeout: 15_000 });
    await expect(card).toContainText(/analyst/i);
  });

  test("stop cancels a running reply and keeps the partial answer", async ({ page }) => {
    await page.goto("/chat");
    await send(page, "hello there, please write a long reply");
    const stop = page.getByTestId("stop-button");
    await expect(stop).toBeVisible();
    await page.waitForTimeout(400);
    await stop.click();
    const reply = page.getByTestId("assistant-message").last();
    await expect(reply).toHaveAttribute("data-status", "cancelled", { timeout: 10_000 });
    await expect(page.getByTestId("send-button")).toBeVisible();
    await page.reload();
    await expect(page.getByTestId("assistant-message").last()).toHaveAttribute("data-status", "cancelled");
  });

  test("conversations can be deleted", async ({ page }) => {
    await page.goto("/chat");
    await send(page, "what time is it?");
    await expect(page.getByTestId("assistant-message").last()).toHaveAttribute("data-status", "done", {
      timeout: 15_000,
    });
    page.once("dialog", (dialog) => dialog.accept());
    const row = page.getByTestId("session-list").locator("div.group").filter({ hasText: "what time is it?" });
    await row.hover();
    await row.getByRole("button", { name: /delete|删除/i }).click();
    await expect(page.getByTestId("session-list")).not.toContainText("what time is it?");
    await expect(page).toHaveURL(/\/chat$/);
  });
});
