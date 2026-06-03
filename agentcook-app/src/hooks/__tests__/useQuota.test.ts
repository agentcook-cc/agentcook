import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

const javaGetMock = vi.fn();

vi.mock("@/api/client", () => ({
  javaClient: {
    get: (url: string) => javaGetMock(url),
  },
}));

import { useQuota } from "../useQuota";

describe("useQuota (ADR-018 cascade — B Day 58)", () => {
  beforeEach(() => {
    javaGetMock.mockReset();
  });

  it("loads quota from /api/v1/quota and computes remaining + isExhausted", async () => {
    javaGetMock.mockResolvedValueOnce({
      free_questions_used: 1,
      free_questions_quota: 2,
    });

    const { result } = renderHook(() => useQuota());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(javaGetMock).toHaveBeenCalledWith("/api/v1/quota");
    expect(result.current.used).toBe(1);
    expect(result.current.quota).toBe(2);
    expect(result.current.remaining).toBe(1);
    expect(result.current.isExhausted).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("flips isExhausted=true when used == quota", async () => {
    javaGetMock.mockResolvedValueOnce({
      free_questions_used: 2,
      free_questions_quota: 2,
    });

    const { result } = renderHook(() => useQuota());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.remaining).toBe(0);
    expect(result.current.isExhausted).toBe(true);
  });

  it("clamps remaining to 0 when used > quota (defensive)", async () => {
    javaGetMock.mockResolvedValueOnce({
      free_questions_used: 5,
      free_questions_quota: 2,
    });

    const { result } = renderHook(() => useQuota());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.remaining).toBe(0);
    expect(result.current.isExhausted).toBe(true);
  });

  it("captures error message when /api/v1/quota fails", async () => {
    javaGetMock.mockRejectedValueOnce(new Error("Network down"));

    const { result } = renderHook(() => useQuota());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Network down");
  });

  it("refetch() re-hits the endpoint and updates state", async () => {
    javaGetMock.mockResolvedValueOnce({
      free_questions_used: 0,
      free_questions_quota: 2,
    });

    const { result } = renderHook(() => useQuota());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.used).toBe(0);

    javaGetMock.mockResolvedValueOnce({
      free_questions_used: 2,
      free_questions_quota: 2,
    });

    await act(async () => {
      await result.current.refetch();
    });

    expect(javaGetMock).toHaveBeenCalledTimes(2);
    expect(result.current.used).toBe(2);
    expect(result.current.isExhausted).toBe(true);
  });
});
