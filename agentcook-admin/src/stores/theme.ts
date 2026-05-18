import { defineStore } from "pinia";
import { ref, watch } from "vue";

type ThemeMode = "light" | "dark" | "system";

function getSystemPreference(): "light" | "dark" {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(mode: ThemeMode) {
  const resolved = mode === "system" ? getSystemPreference() : mode;
  document.documentElement.classList.toggle("dark", resolved === "dark");
}

export const useThemeStore = defineStore("theme", () => {
  const mode = ref<ThemeMode>(
    (localStorage.getItem("theme_mode") as ThemeMode) || "light",
  );

  watch(mode, (newMode) => {
    localStorage.setItem("theme_mode", newMode);
    applyTheme(newMode);
  }, { immediate: true });

  function toggle() {
    mode.value = mode.value === "dark" ? "light" : "dark";
  }

  function setMode(newMode: ThemeMode) {
    mode.value = newMode;
  }

  // 监听系统主题变化
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (mode.value === "system") applyTheme("system");
  });

  return { mode, toggle, setMode };
});
