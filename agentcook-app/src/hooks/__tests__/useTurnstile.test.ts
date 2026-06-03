import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { useTurnstile } from "../useTurnstile";

describe("useTurnstile (Buffer Day 62 — B Step 2)", () => {
  beforeEach(() => {
    document.head.innerHTML = "";
    delete (window as { turnstile?: unknown }).turnstile;
  });

  it("dev mode (empty VITE_TURNSTILE_SITE_KEY): returns sentinel token immediately, ready=true", () => {
    const { result } = renderHook(() => useTurnstile());

    // jsdom test env doesn't define VITE_TURNSTILE_SITE_KEY → empty string
    // → hook returns the dev sentinel without loading the script.
    expect(result.current.token).toBe("dev-mock-turnstile-token");
    expect(result.current.ready).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it("dev mode: containerRef does NOT inject the loader script when site key is empty", () => {
    const { result } = renderHook(() => useTurnstile());

    const div = document.createElement("div");
    act(() => {
      result.current.containerRef(div);
    });

    expect(document.getElementById("cf-turnstile-loader")).toBeNull();
  });

  it("dev mode: reset() restores the sentinel token", () => {
    const { result } = renderHook(() => useTurnstile());

    expect(result.current.token).toBe("dev-mock-turnstile-token");

    act(() => {
      result.current.reset();
    });

    expect(result.current.token).toBe("dev-mock-turnstile-token");
    expect(result.current.ready).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it("does not render a widget when window.turnstile is missing (loader not loaded)", () => {
    const renderSpy = vi.fn();
    const { result } = renderHook(() => useTurnstile());

    const div = document.createElement("div");
    act(() => {
      result.current.containerRef(div);
    });

    // Dev mode short-circuits before reaching window.turnstile.render —
    // the global stays undefined and renderSpy never sees a call.
    expect(renderSpy).not.toHaveBeenCalled();
    expect(window.turnstile).toBeUndefined();
  });

  it("exposes containerRef and reset as stable callable functions", () => {
    const { result } = renderHook(() => useTurnstile());

    expect(typeof result.current.containerRef).toBe("function");
    expect(typeof result.current.reset).toBe("function");

    // Calling containerRef(null) must not throw — the React unmount path
    // passes null to detach the ref, and the hook needs to tolerate it.
    expect(() => result.current.containerRef(null)).not.toThrow();
  });
});
