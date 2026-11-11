import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AuthError, useAuthStore } from "@/stores/auth";
import { useTurnstile } from "@/hooks/useTurnstile";
import { useRuntimeInfo } from "@/hooks/useRuntimeData";

const errorKeys: Record<string, string> = {
  AUTH_INVALID_CREDENTIALS: "credentials",
  AUTH_ACCOUNT_DISABLED: "disabled",
  AUTH_USER_EXISTS: "exists",
  VALIDATION_FAILED: "validation",
  INVALID_ARGUMENT: "validation",
  TURNSTILE_REJECTED: "turnstile",
};

export default function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { login, register, isAuthenticated } = useAuthStore();
  const { data: runtime } = useRuntimeInfo();
  const turnstile = useTurnstile();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isAuthenticated) navigate("/chat", { replace: true });
  }, [isAuthenticated, navigate]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const identity = username.trim();
    const validIdentity = identity.includes("@")
      ? identity.length <= 255 && /^[^@\s]+@[^@\s]+$/.test(identity)
      : /^[A-Za-z0-9_.-]{3,32}$/.test(identity);
    if (!validIdentity || !password.trim() || password.length > 128 || (mode === "register" && password.length < 8)) {
      setError("validation");
      return;
    }
    if (!turnstile.token) {
      setError("turnstile");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await (mode === "login" ? login : register)(identity, password, turnstile.token);
    } catch (failure) {
      setError(failure instanceof AuthError ? (errorKeys[failure.code ?? ""] ?? "server") : "network");
      turnstile.reset();
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm rounded-xl bg-white p-8 shadow-md">
        <h1 className="text-2xl font-bold">{t("auth.brand")}</h1>
        <p className="mt-1 text-sm text-gray-500">{t(`auth.${mode}Description`)}</p>
        <fieldset className="mt-5 flex gap-4" disabled={loading} data-testid="auth-mode-switch">
          <legend className="sr-only">{t("auth.mode")}</legend>
          {(["login", "register"] as const).map((value) => (
            <label key={value} className="flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="radio"
                name="auth-mode"
                value={value}
                checked={mode === value}
                onChange={() => {
                  setMode(value);
                  setError("");
                  setPassword("");
                  turnstile.reset();
                }}
              />
              {t(`auth.${value}`)}
            </label>
          ))}
        </fieldset>
        {error && (
          <div
            role="alert"
            data-testid="auth-error"
            className="mt-4 rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-700"
          >
            {t(`auth.errors.${error}`)}
          </div>
        )}
        <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
          <div>
            <label htmlFor="username" className="mb-1 block text-sm font-medium text-gray-700">
              {t("auth.username")}
            </label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              disabled={loading}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              placeholder={t("auth.usernamePlaceholder")}
            />
          </div>
          <div>
            <label htmlFor="password" className="mb-1 block text-sm font-medium text-gray-700">
              {t("auth.password")}
            </label>
            <input
              id="password"
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={loading}
              aria-describedby={mode === "register" ? "password-hint" : undefined}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              placeholder={t("auth.passwordPlaceholder")}
            />
            {mode === "register" && (
              <p id="password-hint" className="mt-1 text-xs text-gray-500">
                {t("auth.passwordHint")}
              </p>
            )}
          </div>
          <div ref={turnstile.containerRef} data-testid="turnstile-container" className="mt-2" />
          {turnstile.error && (
            <p role="alert" className="text-xs text-red-600" data-testid="turnstile-error">
              {t("auth.errors.turnstile")}
            </p>
          )}
          <button
            type="submit"
            disabled={loading || !turnstile.token}
            data-testid="login-submit"
            className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
          >
            {t(loading ? "auth.submitting" : `auth.${mode}`)}
          </button>
        </form>
        {runtime && runtime.auth_mode !== "required" && (
          <Link to="/chat" className="mt-4 block text-center text-sm text-blue-600">
            {t("auth.guest")}
          </Link>
        )}
      </div>
    </div>
  );
}
