import { createI18n } from "vue-i18n";
import zhCN from "@/locales/zh-CN.json";
import enUS from "@/locales/en-US.json";

/**
 * Day 43 i18n skeleton.
 *
 * Components keep their hardcoded strings for now; we wire vue-i18n at the
 * app root so future commits can replace text with `$t('nav.dashboard')`
 * incrementally without re-doing setup.
 *
 * Locale resolution order:
 *   1. localStorage `agentcook_locale`   (user-pinned override)
 *   2. navigator.language               (browser preference)
 *   3. fallback `zh-CN`                 (China-first product positioning)
 */

export type Locale = "zh-CN" | "en-US";
const SUPPORTED: readonly Locale[] = ["zh-CN", "en-US"];

function detectLocale(): Locale {
  if (typeof window === "undefined") return "zh-CN";
  const stored = localStorage.getItem("agentcook_locale");
  if (stored && (SUPPORTED as readonly string[]).includes(stored)) return stored as Locale;
  const browser = navigator.language;
  if (browser.startsWith("en")) return "en-US";
  return "zh-CN";
}

export const i18n = createI18n({
  legacy: false, // Composition API mode
  globalInjection: true,
  locale: detectLocale(),
  fallbackLocale: "zh-CN",
  messages: {
    "zh-CN": zhCN,
    "en-US": enUS,
  },
});

export function setLocale(locale: Locale) {
  i18n.global.locale.value = locale;
  localStorage.setItem("agentcook_locale", locale);
}
