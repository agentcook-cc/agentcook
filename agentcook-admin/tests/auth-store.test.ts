import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";

// Mock the javaClient before importing the store so the store picks up the mock
vi.mock("@/api/client", () => ({
  javaClient: { post: vi.fn(), get: vi.fn() },
  pythonClient: { post: vi.fn(), get: vi.fn() },
}));

import { useAuthStore } from "@/stores/auth";
import { javaClient } from "@/api/client";

const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (k: string) => store[k] ?? null,
    setItem: (k: string, v: string) => {
      store[k] = String(v);
    },
    removeItem: (k: string) => {
      delete store[k];
    },
    clear: () => {
      store = {};
    },
  };
})();
Object.defineProperty(globalThis, "localStorage", { value: localStorageMock });

describe("auth store · Day 26 Phase 3 wiring", () => {
  beforeEach(() => {
    localStorageMock.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("login persists access_token + token_expires_at to localStorage", async () => {
    const store = useAuthStore();
    vi.mocked(javaClient.post).mockResolvedValueOnce({
      access_token: "dev-token-alice",
      token_type: "Bearer",
      expires_in: 3600,
      refresh_token: "rt-alice",
    });

    await store.login("alice", "secret");

    expect(javaClient.post).toHaveBeenCalledWith("/api/v1/auth/login", {
      username: "alice",
      password: "secret",
    });
    expect(store.accessToken).toBe("dev-token-alice");
    expect(store.refreshToken).toBe("rt-alice");
    expect(localStorage.getItem("access_token")).toBe("dev-token-alice");
    expect(localStorage.getItem("token_expires_at")).toBeTruthy();
    expect(Number(localStorage.getItem("token_expires_at"))).toBeGreaterThan(Date.now());
    expect(store.isAuthenticated).toBe(true);
  });

  it("login accepts camelCase response (D's Jackson default)", async () => {
    const store = useAuthStore();
    vi.mocked(javaClient.post).mockResolvedValueOnce({
      accessToken: "dev-token-alice",
      tokenType: "Bearer",
      expiresIn: 3600,
    });

    await store.login("alice", "secret");

    expect(store.accessToken).toBe("dev-token-alice");
    expect(localStorage.getItem("access_token")).toBe("dev-token-alice");
    expect(store.isAuthenticated).toBe(true);
  });

  it("login propagates server 401 so the view can show a real error", async () => {
    const store = useAuthStore();
    const err = Object.assign(new Error("Request failed with status code 401"), {
      isAxiosError: true,
      response: { status: 401, data: { message: "Invalid credentials" } },
    });
    vi.mocked(javaClient.post).mockRejectedValueOnce(err);

    await expect(store.login("alice", "wrong")).rejects.toBe(err);
    expect(store.isAuthenticated).toBe(false);
    expect(localStorage.getItem("access_token")).toBeNull();
  });

  it("clearAuth wipes both memory and storage", async () => {
    const store = useAuthStore();
    vi.mocked(javaClient.post).mockResolvedValueOnce({
      access_token: "t",
      token_type: "Bearer",
      expires_in: 3600,
    });
    await store.login("alice", "secret");
    expect(store.isAuthenticated).toBe(true);

    store.clearAuth();

    expect(store.accessToken).toBeNull();
    expect(store.refreshToken).toBeNull();
    expect(store.user).toBeNull();
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
    expect(localStorage.getItem("token_expires_at")).toBeNull();
  });

  it("login without refresh_token still succeeds (dev profile)", async () => {
    const store = useAuthStore();
    vi.mocked(javaClient.post).mockResolvedValueOnce({
      access_token: "dev-only",
      token_type: "Bearer",
      expires_in: 60,
    });

    await store.login("alice", "secret");

    expect(store.accessToken).toBe("dev-only");
    expect(store.refreshToken).toBeNull();
    expect(store.isAuthenticated).toBe(true);
  });

  it("refreshAccessToken returns false when no refresh token stored", async () => {
    const store = useAuthStore();
    const ok = await store.refreshAccessToken();
    expect(ok).toBe(false);
    expect(javaClient.post).not.toHaveBeenCalled();
  });
});
