import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import zhCN from "../locales/zh-CN.json";
import enUS from "../locales/en-US.json";

/**
 * Day 43 i18n skeleton for the React surface.
 *
 * Components keep their hardcoded strings for now; this file wires
 * react-i18next at the app root so future commits can replace text with
 * `t('chat.newChat')` incrementally without redoing the bootstrap.
 *
 * Locale resolution mirrors the admin side:
 *   1. localStorage `agentcook_locale`
 *   2. navigator.language
 *   3. fallback `zh-CN`
 */

export type Locale = "zh-CN" | "en-US";
const SUPPORTED: readonly Locale[] = ["zh-CN", "en-US"];

function detectLocale(): Locale {
  if (typeof window === "undefined") return "zh-CN";
  const stored = localStorage.getItem("agentcook_locale");
  if (stored && (SUPPORTED as readonly string[]).includes(stored)) return stored as Locale;
  if (navigator.language.startsWith("en")) return "en-US";
  return "zh-CN";
}

i18n.use(initReactI18next).init({
  resources: {
    "zh-CN": { translation: zhCN },
    "en-US": { translation: enUS },
  },
  lng: detectLocale(),
  fallbackLng: "zh-CN",
  interpolation: { escapeValue: false }, // React already escapes
  returnNull: false,
});

export function setLocale(locale: Locale) {
  i18n.changeLanguage(locale);
  localStorage.setItem("agentcook_locale", locale);
}

export default i18n;
