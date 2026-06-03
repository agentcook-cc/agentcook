/**
 * Phase 6 #24 cascade 第 4 环 — verify useSseChat forwards X-Turnstile-Token
 * via resolveExtraHeaders. Companion to the existing chat round-trip path;
 * does not re-test SSE streaming (covered by Day 28 contract tests).
 */
import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { useSseChat } from "../useSseChat";

const fetchMock = vi.fn();
const originalFetch = globalThis.fetch;

vi.mock("@/stores/auth", () => ({
  useAuthStore: {
    getState: () => ({
      accessToken: "test-access",
      refreshAccessToken: vi.fn().mockResolvedValue(false),
    }),
  },
}));

function fakeResponse(body: string, status = 200): Response {
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(body));
      controller.close();
    },
  });
  return new Response(stream, {
    status,
    headers: { "content-type": "text/event-stream" },
  });
}

describe("useSseChat — Phase 6 #24 X-Turnstile-Token forwarding", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });

  it("forwards X-Turnstile-Token from resolveExtraHeaders into fetch headers", async () => {
    fetchMock.mockResolvedValueOnce(fakeResponse("data: [DONE]\n\n"));

    const { result } = renderHook(() =>
      useSseChat({
        onChunk: () => {},
        onDone: () => {},
        onError: () => {},
        resolveExtraHeaders: () => ({ "X-Turnstile-Token": "mock-token-abc" }),
      }),
    );

    await act(async () => {
      await result.current.send("hello");
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.headers).toMatchObject({
      "X-Turnstile-Token": "mock-token-abc",
      Authorization: "Bearer test-access",
    });
  });

  it("omits X-Turnstile-Token header when resolveExtraHeaders is undefined", async () => {
    fetchMock.mockResolvedValueOnce(fakeResponse("data: [DONE]\n\n"));

    const { result } = renderHook(() =>
      useSseChat({
        onChunk: () => {},
        onDone: () => {},
        onError: () => {},
      }),
    );

    await act(async () => {
      await result.current.send("hello");
    });

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.headers).not.toHaveProperty("X-Turnstile-Token");
    expect(init.headers).toMatchObject({ Authorization: "Bearer test-access" });
  });

  it("re-resolves headers on each send (token refresh between turns)", async () => {
    fetchMock
      .mockResolvedValueOnce(fakeResponse("data: [DONE]\n\n"))
      .mockResolvedValueOnce(fakeResponse("data: [DONE]\n\n"));

    let counter = 0;
    const { result } = renderHook(() =>
      useSseChat({
        onChunk: () => {},
        onDone: () => {},
        onError: () => {},
        resolveExtraHeaders: () => ({ "X-Turnstile-Token": `token-${++counter}` }),
      }),
    );

    await act(async () => {
      await result.current.send("first");
    });
    await act(async () => {
      await result.current.send("second");
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const headers1 = (fetchMock.mock.calls[0][1] as RequestInit).headers;
    const headers2 = (fetchMock.mock.calls[1][1] as RequestInit).headers;
    expect(headers1).toMatchObject({ "X-Turnstile-Token": "token-1" });
    expect(headers2).toMatchObject({ "X-Turnstile-Token": "token-2" });
  });

  afterAll(() => {
    globalThis.fetch = originalFetch;
  });
});

import { afterAll } from "vitest";
