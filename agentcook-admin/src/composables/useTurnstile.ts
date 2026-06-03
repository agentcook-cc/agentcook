import { onUnmounted, ref, type Ref } from "vue";

/**
 * Buffer Day 62 (B Step 2) — admin counterpart of
 * `agentcook-app/src/hooks/useTurnstile.ts`. Same loader strategy,
 * Vue 3 composition surface (refs instead of useState).
 *
 * Dev mode (VITE_TURNSTILE_SITE_KEY empty): returns a sentinel token so
 * login still works against the dev Java backend (which short-circuits
 * verify when `agentcook.turnstile.secret` is empty — commit c3eeb10).
 */

const SCRIPT_ID = "cf-turnstile-loader";
const SCRIPT_URL =
  "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
const DEV_TOKEN = "dev-mock-turnstile-token";

interface TurnstileGlobal {
  render: (
    container: HTMLElement | string,
    options: {
      sitekey: string;
      callback: (token: string) => void;
      "error-callback"?: () => void;
      "expired-callback"?: () => void;
      theme?: "light" | "dark" | "auto";
      size?: "normal" | "compact";
    },
  ) => string;
  reset: (widgetId?: string) => void;
  remove: (widgetId?: string) => void;
}

declare global {
  interface Window {
    turnstile?: TurnstileGlobal;
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

const SITE_KEY =
  (typeof import.meta !== "undefined" &&
    import.meta.env?.VITE_TURNSTILE_SITE_KEY) ||
  "";

export interface UseTurnstileResult {
  token: Ref<string | null>;
  ready: Ref<boolean>;
  error: Ref<string | null>;
  attach: (el: HTMLElement | null) => void;
  reset: () => void;
}

export function useTurnstile(): UseTurnstileResult {
  const token = ref<string | null>(SITE_KEY ? null : DEV_TOKEN);
  const ready = ref<boolean>(!SITE_KEY);
  const error = ref<string | null>(null);
  const widgetId = ref<string | null>(null);

  function renderWidget(el: HTMLElement) {
    if (!SITE_KEY || !window.turnstile) return;
    widgetId.value = window.turnstile.render(el, {
      sitekey: SITE_KEY,
      callback: (t) => {
        token.value = t;
        ready.value = true;
        error.value = null;
      },
      "error-callback": () => {
        token.value = null;
        ready.value = true;
        error.value = "Turnstile challenge failed";
      },
      "expired-callback": () => {
        token.value = null;
      },
      theme: "auto",
      size: "normal",
    });
  }

  function attach(el: HTMLElement | null) {
    if (!SITE_KEY || !el) return;
    loadScript()
      .then(() => renderWidget(el))
      .catch((err) => {
        token.value = null;
        ready.value = true;
        error.value =
          err instanceof Error ? err.message : "Turnstile load failed";
      });
  }

  function reset() {
    if (!SITE_KEY) {
      token.value = DEV_TOKEN;
      ready.value = true;
      error.value = null;
      return;
    }
    if (window.turnstile && widgetId.value) {
      window.turnstile.reset(widgetId.value);
    }
    token.value = null;
  }

  onUnmounted(() => {
    if (SITE_KEY && window.turnstile && widgetId.value) {
      try {
        window.turnstile.remove(widgetId.value);
      } catch {
        // widget already removed (HMR / route swap)
      }
    }
  });

  return { token, ready, error, attach, reset };
}
