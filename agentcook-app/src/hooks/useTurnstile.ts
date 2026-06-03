import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Buffer Day 62 (B Step 2) — minimal Cloudflare Turnstile loader hook.
 *
 * Strategy: load the official `challenges.cloudflare.com/turnstile/v0/api.js`
 * script lazily on first hook mount, render an explicit widget into a host
 * element, and expose the resulting token via React state. No dependency on
 * a third-party React wrapper — keeps the package.json untouched, which
 * matches Day 62 brief code decision §0 (no cross-cutting devDeps until
 * vue-eslint-parser / @typescript-eslint/parser land together).
 *
 * Dev mode: when `VITE_TURNSTILE_SITE_KEY` is empty (default for `vite dev`
 * and CI), the hook returns a sentinel token immediately. The Java
 * `TurnstileVerifier` short-circuits when `agentcook.turnstile.secret` is
 * empty (commit c3eeb10), so login still works end-to-end without a real
 * Cloudflare site provisioned. Prod / staging set the env var, and the
 * widget activates the full challenge flow.
 */

const SCRIPT_ID = "cf-turnstile-loader";
const SCRIPT_URL =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
const DEV_TOKEN = "dev-mock-turnstile-token";

type TurnstileRenderOptions = {
  sitekey: string;
  callback: (token: string) => void;
  "error-callback"?: () => void;
  "expired-callback"?: () => void;
  theme?: "light" | "dark" | "auto";
  size?: "normal" | "compact";
};

declare global {
  interface Window {
    turnstile?: {
      render: (
        container: HTMLElement | string,
        options: TurnstileRenderOptions,
      ) => string;
      reset: (widgetId?: string) => void;
      remove: (widgetId?: string) => void;
    };
  }
}

function loadScript(): Promise<void> {
  if (typeof document === "undefined") return Promise.resolve();
  if (window.turnstile) return Promise.resolve();
  const existing = document.getElementById(
    SCRIPT_ID,
  ) as HTMLScriptElement | null;
  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener(
        "error",
        () => reject(new Error("turnstile script load failed")),
        {
          once: true,
        },
      );
    });
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.id = SCRIPT_ID;
    script.src = SCRIPT_URL;
    script.async = true;
    script.defer = true;
    script.addEventListener("load", () => resolve(), { once: true });
    script.addEventListener(
      "error",
      () => reject(new Error("turnstile script load failed")),
      {
        once: true,
      },
    );
    document.head.appendChild(script);
  });
}

export interface TurnstileState {
  token: string | null;
  ready: boolean;
  error: string | null;
}

export interface UseTurnstileResult extends TurnstileState {
  containerRef: (el: HTMLDivElement | null) => void;
  reset: () => void;
}

const SITE_KEY =
  (typeof import.meta !== "undefined" &&
    import.meta.env?.VITE_TURNSTILE_SITE_KEY) ||
  "";

export function useTurnstile(): UseTurnstileResult {
  const [state, setState] = useState<TurnstileState>({
    token: SITE_KEY ? null : DEV_TOKEN,
    ready: !SITE_KEY,
    error: null,
  });
  const widgetIdRef = useRef<string | null>(null);
  const containerElRef = useRef<HTMLDivElement | null>(null);

  const renderWidget = useCallback((el: HTMLDivElement) => {
    if (!SITE_KEY || !window.turnstile) return;
    widgetIdRef.current = window.turnstile.render(el, {
      sitekey: SITE_KEY,
      callback: (token) => setState({ token, ready: true, error: null }),
      "error-callback": () =>
        setState({
          token: null,
          ready: true,
          error: "Turnstile challenge failed",
        }),
      "expired-callback": () => setState((prev) => ({ ...prev, token: null })),
      theme: "auto",
      size: "normal",
    });
  }, []);

  const containerRef = useCallback(
    (el: HTMLDivElement | null) => {
      containerElRef.current = el;
      if (!SITE_KEY || !el) return;
      loadScript()
        .then(() => renderWidget(el))
        .catch((err) =>
          setState({
            token: null,
            ready: true,
            error: err instanceof Error ? err.message : "Turnstile load failed",
          }),
        );
    },
    [renderWidget],
  );

  const reset = useCallback(() => {
    if (!SITE_KEY) {
      setState({ token: DEV_TOKEN, ready: true, error: null });
      return;
    }
    if (window.turnstile && widgetIdRef.current) {
      window.turnstile.reset(widgetIdRef.current);
    }
    setState((prev) => ({ ...prev, token: null }));
  }, []);

  useEffect(() => {
    return () => {
      if (SITE_KEY && window.turnstile && widgetIdRef.current) {
        try {
          window.turnstile.remove(widgetIdRef.current);
        } catch {
          // widget may already be gone (StrictMode double mount, hot reload)
        }
      }
    };
  }, []);

  return { ...state, containerRef, reset };
}
