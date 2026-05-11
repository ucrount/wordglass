// Theme composable. Reads stored preference, falls back to system preference.

import { onMounted, onUnmounted, ref } from "vue";

const STORAGE_KEY = "wordglass.theme";

type Theme = "light" | "dark";

function getInitial(): Theme {
  if (typeof window === "undefined") return "light";
  const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(t: Theme) {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", t);
  // For native form controls (date pickers, etc.)
  document.documentElement.style.colorScheme = t;
}

export function useTheme() {
  const theme = ref<Theme>(getInitial());
  applyTheme(theme.value);

  function setTheme(t: Theme) {
    theme.value = t;
    localStorage.setItem(STORAGE_KEY, t);
    applyTheme(t);
  }

  function toggle() {
    setTheme(theme.value === "dark" ? "light" : "dark");
  }

  // Sync with system changes if user hasn't picked manually
  let mq: MediaQueryList | null = null;
  function onSystemChange(e: MediaQueryListEvent) {
    if (!localStorage.getItem(STORAGE_KEY)) {
      const t: Theme = e.matches ? "dark" : "light";
      theme.value = t;
      applyTheme(t);
    }
  }

  onMounted(() => {
    if (typeof window === "undefined") return;
    mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", onSystemChange);
  });
  onUnmounted(() => {
    mq?.removeEventListener("change", onSystemChange);
  });

  return { theme, setTheme, toggle };
}
