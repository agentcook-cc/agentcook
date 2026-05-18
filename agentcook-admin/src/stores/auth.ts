import { defineStore } from "pinia";
import { ref, computed } from "vue";

export interface UserInfo {
  id: string;
  username: string;
  displayName: string;
  roles: string[];
}

export const useAuthStore = defineStore("auth", () => {
  const accessToken = ref<string | null>(localStorage.getItem("access_token"));
  const refreshToken = ref<string | null>(localStorage.getItem("refresh_token"));
  const user = ref<UserInfo | null>(null);

  const isAuthenticated = computed(() => !!accessToken.value);
  const hasRole = (role: string) => user.value?.roles.includes(role) ?? false;

  function setTokens(access: string, refresh: string) {
    accessToken.value = access;
    refreshToken.value = refresh;
    localStorage.setItem("access_token", access);
    localStorage.setItem("refresh_token", refresh);
  }

  function clearAuth() {
    accessToken.value = null;
    refreshToken.value = null;
    user.value = null;
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  }

  async function login(username: string, password: string) {
    const response = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!response.ok) throw new Error("Login failed");
    const data = await response.json();
    setTokens(data.access_token, data.refresh_token);
    user.value = data.user;
  }

  async function refreshAccessToken(): Promise<boolean> {
    if (!refreshToken.value) return false;
    try {
      const response = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken.value }),
      });
      if (!response.ok) {
        clearAuth();
        return false;
      }
      const data = await response.json();
      setTokens(data.access_token, data.refresh_token);
      return true;
    } catch {
      clearAuth();
      return false;
    }
  }

  async function fetchUserInfo() {
    if (!accessToken.value) return;
    const response = await fetch("/api/v1/users/me", {
      headers: { Authorization: `Bearer ${accessToken.value}` },
    });
    if (response.status === 401) {
      const refreshed = await refreshAccessToken();
      if (!refreshed) return;
      const retryResponse = await fetch("/api/v1/users/me", {
        headers: { Authorization: `Bearer ${accessToken.value}` },
      });
      if (retryResponse.ok) user.value = await retryResponse.json();
    } else if (response.ok) {
      user.value = await response.json();
    }
  }

  function logout() {
    clearAuth();
  }

  return {
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
