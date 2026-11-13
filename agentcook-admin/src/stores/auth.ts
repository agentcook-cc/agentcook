import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { javaClient } from "@/api/client";
import type { components } from "@/api/types.java.gen";

export interface UserInfo {
  id: string;
  username: string;
  displayName: string;
  roles: string[];
}

/** Java returns camelCase token envelopes; older adapters may still use snake_case. */
interface LoginResponseSnake {
  access_token?: string;
  token_type?: string;
  expires_in?: number;
  refresh_token?: string;
  user?: UserInfo;
}
interface LoginResponseCamel {
  accessToken?: string;
  tokenType?: string;
  expiresIn?: number;
  refreshToken?: string;
  user?: UserInfo;
}
type LoginResponse = LoginResponseSnake & LoginResponseCamel;
type RefreshResponse = LoginResponse;

function normaliseTokens(data: LoginResponse): {
  access: string;
  refresh?: string;
  expiresIn: number;
} {
  const access = data.access_token ?? data.accessToken;
  const refresh = data.refresh_token ?? data.refreshToken;
  const expiresIn = data.expires_in ?? data.expiresIn ?? 3600;
  if (!access) throw new Error("Auth response missing access token field");
  return { access, refresh, expiresIn };
}

// UserResponse is the generated DTO; if D ships /users/me with a richer
// shape (username, displayName, roles) we adapt at the mapper.
type UserResponseDto = components["schemas"]["UserResponse"];

/** UI gate only; API authorization is enforced by the server. */
export function isAdminToken(token: string | null): boolean {
  if (!token) return false;
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return false;
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const bytes = Uint8Array.from(atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, "=")), (c) => c.charCodeAt(0));
    const payload = JSON.parse(new TextDecoder().decode(bytes));
    if (payload.typ === "refresh" || payload.token_type === "refresh") return false;
    return (
      (Array.isArray(payload.roles) && payload.roles.includes("admin")) ||
      (typeof payload.scope === "string" && payload.scope.split(/\s+/).includes("admin"))
    );
  } catch {
    return false;
  }
}

export const useAuthStore = defineStore("auth", () => {
  const accessToken = ref<string | null>(localStorage.getItem("access_token"));
  const refreshToken = ref<string | null>(localStorage.getItem("refresh_token"));
  const tokenExpiresAt = ref<number | null>(Number(localStorage.getItem("token_expires_at")) || null);
  const user = ref<UserInfo | null>(null);
  const authError = ref("");

  const isAuthenticated = computed(() => isAdminToken(accessToken.value));
  const hasRole = (role: string) => user.value?.roles.includes(role) ?? false;

  function setTokens(access: string, refresh: string | undefined, expiresIn: number) {
    if (!isAdminToken(access)) {
      clearAuth();
      authError.value = "该账号没有管理员权限";
      throw new Error(authError.value);
    }
    authError.value = "";
    accessToken.value = access;
    localStorage.setItem("access_token", access);
    refreshToken.value = refresh ?? null;
    if (refresh) localStorage.setItem("refresh_token", refresh);
    else localStorage.removeItem("refresh_token");
    const expiresAt = Date.now() + expiresIn * 1000;
    tokenExpiresAt.value = expiresAt;
    localStorage.setItem("token_expires_at", String(expiresAt));
  }

  function clearAuth() {
    accessToken.value = null;
    refreshToken.value = null;
    tokenExpiresAt.value = null;
    user.value = null;
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("token_expires_at");
  }

  async function login(username: string, password: string, turnstileToken?: string | null) {
    const data = await javaClient.post<LoginResponse>("/api/v1/auth/login", {
      username,
      password,
      turnstileToken: turnstileToken ?? undefined,
    });
    const { access, refresh, expiresIn } = normaliseTokens(data);
    setTokens(access, refresh, expiresIn);
    if (data.user) {
      user.value = data.user;
    } else {
      // dev profile may not embed user; fetch it lazily
      await fetchUserInfo().catch(() => {
        // tolerate /users/me 404 in early dev — token alone is enough to enter
      });
    }
  }

  async function refreshAccessToken(): Promise<boolean> {
    if (!refreshToken.value) return false;
    try {
      const data = await javaClient.post<RefreshResponse>("/api/v1/auth/refresh", { refreshToken: refreshToken.value });
      const { access, refresh, expiresIn } = normaliseTokens(data);
      setTokens(access, refresh, expiresIn);
      return true;
    } catch {
      clearAuth();
      return false;
    }
  }

  async function fetchUserInfo() {
    if (!accessToken.value) return;
    try {
      const data = await javaClient.get<
        UserResponseDto & {
          username?: string;
          displayName?: string;
          roles?: string[];
        }
      >("/api/v1/users/me");
      user.value = {
        id: String(data.id ?? "unknown"),
        username: data.username ?? data.email ?? "unknown",
        displayName: data.displayName ?? data.nickname ?? data.username ?? "User",
        roles: data.roles ?? [],
      };
    } catch {
      // swallow — caller decides whether absence of user is fatal
    }
  }

  function logout() {
    clearAuth();
  }

  if (accessToken.value && !isAdminToken(accessToken.value)) {
    clearAuth();
    authError.value = "该账号没有管理员权限";
  }

  return {
    authError,
    accessToken,
    refreshToken,
    user,
    isAuthenticated,
    hasRole,
    login,
    logout,
    refreshAccessToken,
    fetchUserInfo,
    clearAuth,
  };
});
