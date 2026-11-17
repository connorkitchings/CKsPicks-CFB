"use client";

import { useEffect } from "react";

/**
 * Re-applies the saved theme after mount. When `notFound()` fires after a loading shell has streamed,
 * the client renders the page itself and the pre-paint script in `ThemeScript` never runs for it, so
 * the `dark` class can be missing. Same rule as that script.
 */
export function ThemeReapply() {
  useEffect(() => {
    try {
      const saved = localStorage.getItem("theme");
      const dark = saved === "dark" || ((!saved || saved === "system") && window.matchMedia("(prefers-color-scheme: dark)").matches);
      document.documentElement.classList.toggle("dark", dark);
    } catch {}
  }, []);
  return null;
}
