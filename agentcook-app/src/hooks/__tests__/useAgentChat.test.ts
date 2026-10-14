import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { transcriptToMessages, useAgentChat } from "../useAgentChat";

const cancelRun = vi.fn();
vi.mock("@/api/runtime", () => ({ runtimeApi: { cancelRun: (id: string) => cancelRun(id) } }));

const authState = {
  accessToken: "tok" as string | null,
  refreshToken: null as string | null,
  refreshAccessToken: vi.fn().mockResolvedValue(false),
};
vi.mock("@/stores/auth", () => ({ useAuthStore: { getState: () => authState } }));

const fetchMock = vi.fn();

function sse(...frames: object[]): Response {
  const body = frames.map((f) => `data: ${JSON.stringify(f)}\n\n`).join("");
  return new Response(
    new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(body));
        controller.close();
      },
    }),
    { status: 200, headers: { "content-type": "text/event-stream" } },
  );
}

beforeEach(() => {
  fetchMock.mockReset();
  cancelRun.mockReset();
  globalThis.fetch = fetchMock as unknown as typeof fetch;
  authState.accessToken = "tok";
});

describe("useAgentChat", () => {
  it("streams text, upserts tool calls and records run metadata", async () => {
    fetchMock.mockResolvedValueOnce(
      sse(
        { type: "start", run_id: "run_1", session_id: "s", metadata: { agent: "assistant", model: "m" } },
        {
          type: "tool_call",
          tool_call: { id: "c1", name: "calculator", arguments: { expression: "1+1" }, status: "running" },
        },
        {
          type: "tool_result",
          tool_call: { id: "c1", name: "calculator", arguments: { expression: "1+1" }, status: "success", output: "2" },
        },
        { type: "delta", content: "It is " },
        { type: "delta", content: "2." },
        {
          type: "done",
          done: true,
          metadata: { usage: { input_tokens: 5, output_tokens: 3, total_tokens: 8 }, finish_reason: "stop" },
        },
      ),
    );
    const { result } = renderHook(() => useAgentChat());
    await act(async () => {
      await result.current.send({ sessionId: "s", text: "1+1?", agent: "assistant", pluginIds: ["web"] });
    });

    const [init] = fetchMock.mock.calls.map((c) => c[1] as RequestInit);
    expect(JSON.parse(init.body as string)).toEqual({
      session_id: "s",
      message: "1+1?",
      agent: "assistant",
      plugin_ids: ["web"],
    });
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer tok");

    const [user, assistant] = result.current.messages;
    expect(user).toMatchObject({ role: "user", content: "1+1?" });
    expect(assistant.content).toBe("It is 2.");
    expect(assistant.status).toBe("done");
    expect(assistant.toolCalls).toHaveLength(1);
    expect(assistant.toolCalls[0]).toMatchObject({ status: "success", output: "2" });
    expect(assistant.meta).toMatchObject({ agent: "assistant", model: "m", finish_reason: "stop" });
    expect(result.current.streaming).toBe(false);
  });

  it("omits Authorization for anonymous use", async () => {
    authState.accessToken = null;
    fetchMock.mockResolvedValueOnce(sse({ type: "done", done: true }));
    const { result } = renderHook(() => useAgentChat());
    await act(async () => {
      await result.current.send({ sessionId: "s", text: "hi" });
    });
    const headers = (fetchMock.mock.calls[0][1] as RequestInit).headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
  });

  it("surfaces the runtime's error envelope", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ code: "SESSION_BUSY", message: "This session is already generating a reply" }), {
        status: 409,
        headers: { "content-type": "application/json" },
      }),
    );
    const { result } = renderHook(() => useAgentChat());
    await act(async () => {
      await result.current.send({ sessionId: "s", text: "hi" });
    });
    const assistant = result.current.messages[1];
    expect(assistant.status).toBe("error");
    expect(assistant.error).toContain("already generating");
  });

  it("marks error frames and truncated streams as failures", async () => {
    fetchMock.mockResolvedValueOnce(sse({ type: "error", done: true, error: "RuntimeError: upstream" }));
    const { result } = renderHook(() => useAgentChat());
    await act(async () => {
      await result.current.send({ sessionId: "s", text: "a" });
    });
    expect(result.current.messages[1]).toMatchObject({ status: "error", error: "RuntimeError: upstream" });

    fetchMock.mockResolvedValueOnce(sse({ type: "delta", content: "partial" }));
    await act(async () => {
      await result.current.send({ sessionId: "s", text: "b" });
    });
    const truncated = result.current.messages[3];
    expect(truncated.status).toBe("error");
    expect(truncated.content).toBe("partial");
  });

  it("cancelled runs settle as cancelled", async () => {
    fetchMock.mockResolvedValueOnce(
      sse({ type: "delta", content: "half" }, { type: "done", done: true, metadata: { finish_reason: "cancelled" } }),
    );
    const { result } = renderHook(() => useAgentChat());
    await act(async () => {
      await result.current.send({ sessionId: "s", text: "go" });
    });
    expect(result.current.messages[1]).toMatchObject({ status: "cancelled", content: "half" });
  });

  it("stop() cancels the server-side run when one is active", async () => {
    let release: () => void = () => {};
    fetchMock.mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          release = () => resolve(sse({ type: "done", done: true, metadata: { finish_reason: "cancelled" } }));
        }),
    );
    cancelRun.mockResolvedValue({ cancelled: true });
    const { result } = renderHook(() => useAgentChat());
    let pending: Promise<void> = Promise.resolve();
    act(() => {
      pending = result.current.send({ sessionId: "s", text: "go" });
    });
    expect(result.current.streaming).toBe(true);
    // No run id yet (no start frame) → stop falls back to a local abort.
    await act(async () => {
      await result.current.stop();
    });
    expect(cancelRun).not.toHaveBeenCalled();
    release();
    await act(async () => {
      await pending;
    });
    expect(result.current.streaming).toBe(false);
  });

  it("calls onTurnFinished after every turn", async () => {
    const onTurnFinished = vi.fn();
    fetchMock.mockResolvedValueOnce(sse({ type: "done", done: true }));
    const { result } = renderHook(() => useAgentChat({ onTurnFinished }));
    await act(async () => {
      await result.current.send({ sessionId: "s", text: "hi" });
    });
    expect(onTurnFinished).toHaveBeenCalledTimes(1);
  });
});

describe("transcriptToMessages", () => {
  it("maps statuses from metadata", () => {
    const messages = transcriptToMessages([
      { id: "1", role: "user", content: "q", tool_calls: [], metadata: {} },
      { id: "2", role: "assistant", content: "a", tool_calls: [], metadata: { finish_reason: "cancelled" } },
      { id: "3", role: "assistant", content: "", tool_calls: [], metadata: { error: "boom" } },
    ]);
    expect(messages.map((m) => m.status)).toEqual(["done", "cancelled", "error"]);
    expect(messages[2].error).toBe("boom");
  });
});
