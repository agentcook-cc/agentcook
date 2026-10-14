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
  setTokens: (access: string, refresh?: string | null) => void;
  setUser: (user: UserInfo) => void;
  clearAuth: () => void;
  login: (username: string, password: string, turnstileToken?: string | null) => Promise<void>;
  refreshAccessToken: () => Promise<boolean>;
  fetchUserInfo: () => Promise<void>;
}

const ACCESS_KEY = "access_token";
const REFRESH_KEY = "refresh_token";

function javaBase(): string {
  return (typeof import.meta !== "undefined" && import.meta.env?.VITE_JAVA_API_BASE_URL) || "";
}

function readStored(key: string): string | null {
  const value = localStorage.getItem(key);
  // Earlier builds persisted the literal string "undefined" when the
  // login response carried no refresh token — treat it as absent.
  return value && value !== "undefined" && value !== "null" ? value : null;
}

/** Map agentcook-java's UserResponse (or an already-shaped UserInfo). */
export function toUserInfo(raw: Record<string, unknown>): UserInfo {
  const id = String(raw.id ?? "");
  const email = typeof raw.email === "string" ? raw.email : "";
  const username = typeof raw.username === "string" ? raw.username : email.split("@")[0] || id;
  const displayName =
    (typeof raw.displayName === "string" && raw.displayName) ||
    (typeof raw.nickname === "string" && raw.nickname) ||
    username;
  return { id, username, displayName };
}

/** Accept both camelCase (Java) and snake_case token envelopes. */
function readTokens(data: Record<string, unknown>): { access?: string; refresh?: string } {
  const access = (data.accessToken ?? data.access_token) as string | undefined;
  const refresh = (data.refreshToken ?? data.refresh_token) as string | undefined;
  return { access, refresh };
}

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: readStored(ACCESS_KEY),
  refreshToken: readStored(REFRESH_KEY),
  user: null,
  isAuthenticated: !!readStored(ACCESS_KEY),

  setTokens(access: string, refresh?: string | null) {
    localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
    else localStorage.removeItem(REFRESH_KEY);
    set({ accessToken: access, refreshToken: refresh ?? null, isAuthenticated: true });
  },

  setUser(user: UserInfo) {
    set({ user });
  },

  clearAuth() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    set({ accessToken: null, refreshToken: null, user: null, isAuthenticated: false });
  },

  async login(username: string, password: string, turnstileToken?: string | null) {
    const response = await fetch(`${javaBase()}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, turnstileToken: turnstileToken ?? undefined }),
    });
    if (!response.ok) throw new Error(response.status === 401 ? "Invalid credentials" : "Login failed");
    const data = (await response.json()) as Record<string, unknown>;
    const { access, refresh } = readTokens(data);
    if (!access) throw new Error("Login response carried no access token");
    get().setTokens(access, refresh);
    if (data.user && typeof data.user === "object") {
      set({ user: toUserInfo(data.user as Record<string, unknown>) });
    } else {
      void get().fetchUserInfo();
    }
  },

  async refreshAccessToken(): Promise<boolean> {
    const { refreshToken, clearAuth, setTokens } = get();
    if (!refreshToken) return false;
    try {
      const response = await fetch(`${javaBase()}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refreshToken }),
      });
      if (!response.ok) {
        clearAuth();
        return false;
      }
      const { access, refresh } = readTokens((await response.json()) as Record<string, unknown>);
      if (!access) {
        clearAuth();
        return false;
      }
      setTokens(access, refresh ?? refreshToken);
      return true;
    } catch {
      clearAuth();
      return false;
    }
  },

  async fetchUserInfo() {
    const { accessToken, refreshAccessToken, clearAuth } = get();
    if (!accessToken) return;
    const load = (token: string) =>
      fetch(`${javaBase()}/api/v1/users/me`, { headers: { Authorization: `Bearer ${token}` } });
    try {
      let response = await load(accessToken);
      if (response.status === 401) {
        if (!(await refreshAccessToken())) return;
        response = await load(get().accessToken ?? "");
        if (!response.ok) {
          clearAuth();
          return;
        }
      }
      if (response.ok) set({ user: toUserInfo((await response.json()) as Record<string, unknown>) });
    } catch {
      // Java unreachable — keep the token; the display name stays empty.
    }
  },
}));
