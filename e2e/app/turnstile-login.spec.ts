/**
 * app LoginPage Turnstile widget — Buffer Day 62 (B Step 2).
 *
 * Cascade context (commit c3eeb10 / D Day 62):
 *   - Java AuthController.login() now requires LoginRequest.turnstileToken
 *     when `agentcook.turnstile.secret` is set; dev / test profile keeps
 *     the verifier short-circuited so the dev backend accepts the
 *     `dev-mock-turnstile-token` sentinel that useTurnstile emits when
 *     `VITE_TURNSTILE_SITE_KEY` is empty.
 *
 * This spec runs against the dev build (no real Cloudflare site), so the
 * widget never paints — the hook returns the sentinel synchronously and
 * the form is submittable. We assert: (a) the container is in the DOM,
 * (b) the submit button is enabled (token sentinel populated), (c) form
 * still validates username/password before signing in.
 *
 * Real Turnstile challenge flow (paint + token resolve) is verified
 * manually post-prod-deploy using the staging site key — automating it
 * needs Cloudflare's playground site keys + iframe instrumentation,
 * which is a separate Buffer item.
 */
import { test, expect } from "@playwright/test";

test.describe("app LoginPage — Turnstile widget (dev sentinel)", () => {
  test("renders Turnstile container and enables submit when token is present", async ({
    page,
  }) => {
    await page.goto("/login");

    await expect(page.getByTestId("turnstile-container")).toBeAttached();

    // Dev mode (empty VITE_TURNSTILE_SITE_KEY) populates the sentinel
    // token immediately, so the submit button is not disabled by the
    // missing-token gate. Username + password are still required.
    const submit = page.getByTestId("login-submit");
    await expect(submit).toBeEnabled();

    // Submitting without credentials surfaces the username/password
    // error rather than the Turnstile gate (proves the token check
    // came after the form-validation early-return).
    await submit.click();
    await expect(
      page.getByText("Please enter username and password"),
    ).toBeVisible();
  });
});
