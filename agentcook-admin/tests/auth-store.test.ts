import { describe, it, expect, beforeEach, vi } from "vitest";
import { setActivePinia, createPinia } from "pinia";

// Mock the javaClient before importing the store so the store picks up the mock
vi.mock("@/api/client", () => ({
  javaClient: { post: vi.fn(), get: vi.fn() },
  pythonClient: { post: vi.fn(), get: vi.fn() },
}));

import { isAdminToken, useAuthStore } from "@/stores/auth";
import { javaClient } from "@/api/client";

function token(payload: Record<string, unknown> = { roles: ["user", "admin"], typ: "access" }) {
  return `header.${Buffer.from(JSON.stringify(payload)).toString("base64url")}.signature`;
}

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
      access_token: token(),
      token_type: "Bearer",
      expires_in: 3600,
      refresh_token: "rt-alice",
    });

    await store.login("alice", "secret");

    expect(javaClient.post).toHaveBeenCalledWith("/api/v1/auth/login", {
      username: "alice",
      password: "secret",
    });
    expect(store.accessToken).toBe(token());
    expect(store.refreshToken).toBe("rt-alice");
    expect(localStorage.getItem("access_token")).toBe(token());
    expect(localStorage.getItem("token_expires_at")).toBeTruthy();
    expect(Number(localStorage.getItem("token_expires_at"))).toBeGreaterThan(Date.now());
    expect(store.isAuthenticated).toBe(true);
  });

  it("login accepts camelCase response (D's Jackson default)", async () => {
    const store = useAuthStore();
    vi.mocked(javaClient.post).mockResolvedValueOnce({
      accessToken: token(),
      tokenType: "Bearer",
      expiresIn: 3600,
    });

    await store.login("alice", "secret");

    expect(store.accessToken).toBe(token());
    expect(localStorage.getItem("access_token")).toBe(token());
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
      access_token: token(),
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
      access_token: token(),
      token_type: "Bearer",
      expires_in: 60,
    });

    await store.login("alice", "secret");

    expect(store.accessToken).toBe(token());
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

describe("admin authorization", () => {
  beforeEach(() => {
    localStorageMock.clear();
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("accepts roles or space-separated scope with base64url and unicode", () => {
    expect(isAdminToken(token({ scope: "chat admin", preferred_username: "管理员" }))).toBe(true);
    expect(isAdminToken(token({ roles: ["admin"] }))).toBe(true);
    expect(isAdminToken(token({ scope: "superadmin" }))).toBe(false);
    expect(isAdminToken(token({ roles: ["admin"], typ: "refresh" }))).toBe(false);
    expect(isAdminToken("broken")).toBe(false);
  });

  it("rejects non-admin login and clears existing tokens", async () => {
    const store = useAuthStore();
    vi.mocked(javaClient.post).mockResolvedValueOnce({
      accessToken: token({ roles: ["user"] }),
      refreshToken: "refresh",
    });
    await expect(store.login("alice", "password")).rejects.toThrow("该账号没有管理员权限");
    expect(store.isAuthenticated).toBe(false);
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });

  it("rejects stored ordinary-user tokens at startup", () => {
    localStorage.setItem("access_token", token({ roles: ["user"] }));
    localStorage.setItem("refresh_token", "refresh");
    const store = useAuthStore();
    expect(store.isAuthenticated).toBe(false);
    expect(store.authError).toBe("该账号没有管理员权限");
    expect(localStorage.getItem("refresh_token")).toBeNull();
  });

  it("uses the refresh contract and rejects a demoted account", async () => {
    localStorage.setItem("access_token", token());
    localStorage.setItem("refresh_token", "refresh");
    const store = useAuthStore();
    vi.mocked(javaClient.post).mockResolvedValueOnce({ accessToken: token({ roles: ["user"] }), refreshToken: "new" });
    expect(await store.refreshAccessToken()).toBe(false);
    expect(javaClient.post).toHaveBeenCalledWith("/api/v1/auth/refresh", { refreshToken: "refresh" });
    expect(store.isAuthenticated).toBe(false);
    expect(store.authError).toBe("该账号没有管理员权限");
  });
});
