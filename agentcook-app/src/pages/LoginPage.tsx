import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/auth";
import { useTurnstile } from "@/hooks/useTurnstile";

export default function LoginPage() {
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const turnstile = useTurnstile();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (isAuthenticated) {
      navigate("/chat", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!username || !password) {
      setError("Please enter username and password");
      return;
    }
    if (!turnstile.token) {
      setError("Please complete the Turnstile challenge before signing in");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await login(username, password, turnstile.token);
    } catch {
      setError("Invalid credentials. Please try again.");
      turnstile.reset();
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm rounded-xl bg-white p-8 shadow-md">
        <h1 className="text-2xl font-bold">AgentCook</h1>
        <p className="mt-1 text-sm text-gray-500">Sign in to continue</p>

        {error && (
          <div className="mt-4 rounded-lg bg-red-50 px-4 py-2.5 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              disabled={loading}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              placeholder="Enter username"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={loading}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              placeholder="Enter password"
            />
          </div>
          <div
            ref={turnstile.containerRef}
            data-testid="turnstile-container"
            className="mt-2"
          />
          {turnstile.error && (
            <p className="text-xs text-red-600" data-testid="turnstile-error">
              {turnstile.error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading || !turnstile.token}
            data-testid="login-submit"
            className="w-full rounded-lg bg-blue-600 py-2.5 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
