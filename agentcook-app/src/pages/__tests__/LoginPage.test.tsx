import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LoginPage from "../LoginPage";
import { AuthError, useAuthStore } from "@/stores/auth";
import i18n from "@/i18n";

const state = vi.hoisted(() => ({ auth_mode: "required", reset: vi.fn() }));
vi.mock("@/hooks/useRuntimeData", () => ({ useRuntimeInfo: () => ({ data: { auth_mode: state.auth_mode } }) }));
vi.mock("@/hooks/useTurnstile", () => ({
  useTurnstile: () => ({ token: "verified", reset: state.reset, containerRef: null, error: null }),
}));

function fill(password = "password-123") {
  fireEvent.change(screen.getByLabelText("用户名或邮箱"), { target: { value: "alice" } });
  fireEvent.change(screen.getByLabelText("密码"), { target: { value: password } });
}

beforeEach(async () => {
  await i18n.changeLanguage("zh-CN");
  state.auth_mode = "required";
  useAuthStore.setState({ isAuthenticated: false, login: vi.fn(), register: vi.fn() });
});

describe("account entry", () => {
  it("registers through an accessible mode switch and changes password autocomplete", async () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    expect(screen.getByLabelText("密码")).toHaveAttribute("autocomplete", "current-password");
    fireEvent.click(screen.getByLabelText("注册"));
    expect(screen.getByLabelText("密码")).toHaveAttribute("autocomplete", "new-password");
    fill();
    fireEvent.click(screen.getByTestId("login-submit"));
    await waitFor(() =>
      expect(useAuthStore.getState().register).toHaveBeenCalledWith("alice", "password-123", "verified"),
    );
    expect(useAuthStore.getState().login).not.toHaveBeenCalled();
  });

  it("rejects short registration passwords before sending a request", () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByLabelText("注册"));
    fill("short");
    fireEvent.click(screen.getByTestId("login-submit"));
    expect(screen.getByRole("alert")).toHaveTextContent("8–128");
    expect(useAuthStore.getState().register).not.toHaveBeenCalled();
  });

  it.each([
    ["AUTH_INVALID_CREDENTIALS", "用户名或密码错误"],
    ["AUTH_ACCOUNT_DISABLED", "账号已停用"],
    ["AUTH_USER_EXISTS", "已被注册"],
    ["VALIDATION_FAILED", "有效邮箱"],
    ["TURNSTILE_REJECTED", "人机验证"],
  ])("shows an actionable error for %s", async (code, message) => {
    vi.mocked(useAuthStore.getState().login).mockRejectedValue(new AuthError(401, code, "server text"));
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    fill();
    fireEvent.click(screen.getByTestId("login-submit"));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(message));
  });

  it("shows network failures and allows guest access only when runtime permits it", async () => {
    state.auth_mode = "optional";
    vi.mocked(useAuthStore.getState().login).mockRejectedValue(new TypeError("fetch failed"));
    const { unmount } = render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    fill();
    expect(screen.getByRole("link", { name: "先不登录，直接体验" })).toHaveAttribute("href", "/chat");
    fireEvent.click(screen.getByTestId("login-submit"));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("网络连接失败"));
    unmount();
    state.auth_mode = "required";
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("link")).toBeNull();
  });
});
