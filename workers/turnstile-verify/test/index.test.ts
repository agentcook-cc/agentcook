/**
 * Turnstile verify Worker — unit tests
 *
 * 跑:pnpm test(vitest)
 *
 * 5 场景对照 design doc §6.1:
 *   1. 空 secret 跳过(env 缺配 → 500 WORKER_MISCONFIGURED)
 *   2. 真 token 200(mock siteverify success: true)
 *   3. 假 token 401(mock siteverify success: false)
 *   4. Cloudflare 504 → 503(siteverify HTTP 5xx)
 *   5. token 缺失 → 400 MISSING_TOKEN
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import worker from "../src/index";

interface Env {
  TURNSTILE_SECRET: string;
  TURNSTILE_BYPASS?: string;
}

const baseEnv: Env = {
  TURNSTILE_SECRET: "1x0000000000000000000000000000000AA", // Cloudflare 官方 always-pass test secret
};

function makeRequest(body: unknown): Request {
  return new Request("https://worker.dev/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("turnstile-verify Worker", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("WORKER_MISCONFIGURED when TURNSTILE_SECRET empty", async () => {
    const env: Env = { TURNSTILE_SECRET: "" };
    const res = await worker.fetch(makeRequest({ token: "x" }), env);
    expect(res.status).toBe(500);
    const json = await res.json();
    expect(json).toMatchObject({
      success: false,
      error: "WORKER_MISCONFIGURED",
    });
  });

  it("MISSING_TOKEN when token absent", async () => {
    const res = await worker.fetch(makeRequest({}), baseEnv);
    expect(res.status).toBe(400);
    const json = await res.json();
    expect(json).toMatchObject({ success: false, error: "MISSING_TOKEN" });
  });

  it("returns 200 success on real Cloudflare success: true", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: true,
            challenge_ts: "2026-06-05T12:00:00Z",
            hostname: "agentcook.cc",
          }),
          { status: 200 },
        ),
      ),
    );
    const res = await worker.fetch(
      makeRequest({ token: "real-token", remoteIp: "1.2.3.4" }),
      baseEnv,
    );
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json).toMatchObject({ success: true, hostname: "agentcook.cc" });
  });

  it("returns 401 on Cloudflare success: false", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            success: false,
            error_codes: ["invalid-input-response"],
          }),
          { status: 200 },
        ),
      ),
    );
    const res = await worker.fetch(
      makeRequest({ token: "fake-token" }),
      baseEnv,
    );
    expect(res.status).toBe(401);
    const json = await res.json();
    expect(json).toMatchObject({
      success: false,
      error: "VERIFICATION_FAILED",
    });
  });

  it("returns 503 when siteverify HTTP 5xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("upstream", { status: 504 })),
    );
    const res = await worker.fetch(makeRequest({ token: "x" }), baseEnv);
    expect(res.status).toBe(503);
    const json = await res.json();
    expect(json).toMatchObject({
      success: false,
      error: "SITEVERIFY_HTTP_504",
    });
  });

  it("BYPASS env returns 200 without calling siteverify", async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const res = await worker.fetch(makeRequest({ token: "x" }), {
      ...baseEnv,
      TURNSTILE_BYPASS: "true",
    });
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json).toMatchObject({ success: true, bypass: true });
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
