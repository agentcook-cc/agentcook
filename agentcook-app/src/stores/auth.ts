import { create } from "zustand";

export interface UserInfo {
  id: string;
  username: string;
  displayName: string;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: UserInfo | null;
  isAuthenticated: boolean;
  setTokens: (access: string, refresh: string) => void;
  setUser: (user: UserInfo) => void;
  clearAuth: () => void;
  login: (
    username: string,
    password: string,
    turnstileToken?: string | null,
  ) => Promise<void>;
  refreshAccessToken: () => Promise<boolean>;
  fetchUserInfo: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: localStorage.getItem("access_token"),
  refreshToken: localStorage.getItem("refresh_token"),
  user: null,
  isAuthenticated: !!localStorage.getItem("access_token"),

  setTokens(access: string, refresh: string) {
    localStorage.setItem("access_token", access);
    localStorage.setItem("refresh_token", refresh);
    set({ accessToken: access, refreshToken: refresh, isAuthenticated: true });
  },

  setUser(user: UserInfo) {
    set({ user });
  },

  clearAuth() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
    });
  },

  async login(
    username: string,
    password: string,
    turnstileToken?: string | null,
  ) {
    const javaBase =
      (typeof import.meta !== "undefined" &&
        import.meta.env?.VITE_JAVA_API_BASE_URL) ||
      "";
    const response = await fetch(`${javaBase}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username,
        password,
        turnstileToken: turnstileToken ?? undefined,
      }),
    });
    if (!response.ok) throw new Error("Login failed");
    const data = await response.json();
    const accessToken = data.access_token ?? data.accessToken;
    const refreshTokenValue = data.refresh_token ?? data.refreshToken;
    get().setTokens(accessToken, refreshTokenValue);
    if (data.user) {
      set({ user: data.user });
    }
  },

  async refreshAccessToken(): Promise<boolean> {
    const { refreshToken, clearAuth, setTokens } = get();
    if (!refreshToken) return false;
    try {
      const javaBase =
        (typeof import.meta !== "undefined" &&
          import.meta.env?.VITE_JAVA_API_BASE_URL) ||
        "";
      const response = await fetch(`${javaBase}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken, refreshToken }),
      });
      if (!response.ok) {
        clearAuth();
        return false;
      }
      const data = await response.json();
      const accessToken = data.access_token ?? data.accessToken;
      const refreshTokenValue = data.refresh_token ?? data.refreshToken;
      setTokens(accessToken, refreshTokenValue);
      return true;
    } catch {
      clearAuth();
      return false;
    }
  },

  async fetchUserInfo() {
    const { accessToken, refreshAccessToken, clearAuth } = get();
    if (!accessToken) return;
    const javaBase =
      (typeof import.meta !== "undefined" &&
        import.meta.env?.VITE_JAVA_API_BASE_URL) ||
      "";
    const response = await fetch(`${javaBase}/api/v1/users/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (response.status === 401) {
      const refreshed = await refreshAccessToken();
      if (!refreshed) return;
      const retryResponse = await fetch(`${javaBase}/api/v1/users/me`, {
        headers: { Authorization: `Bearer ${get().accessToken}` },
      });
      if (retryResponse.ok) set({ user: await retryResponse.json() });
      else clearAuth();
    } else if (response.ok) {
      set({ user: await response.json() });
    }
  },
}));
