"use client";

import { useSyncExternalStore } from "react";
import clsx from "clsx";

/**
 * Manual light/dark/system toggle.
 *
 * The init script in app/layout.tsx runs before paint and sets the `.dark`
 * class on <html> based on localStorage.theme (defaulting to "system" when
 * unset, which defers to prefers-color-scheme). This button persists the
 * user's explicit choice and updates the class immediately.
 *
 * The current value is read via useSyncExternalStore so it works correctly
 * across SSR (returns "system") and hydration (returns the stored value).
 */
type Theme = "light" | "dark" | "system";

const ORDER: Theme[] = ["light", "dark", "system"];

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  const prefersDark = window.matchMedia(
    "(prefers-color-scheme: dark)",
  ).matches;
  const dark = theme === "dark" || (theme === "system" && prefersDark);
  root.classList.toggle("dark", dark);
  // Keep in step with --surface-page (and the theme script in app/layout.tsx).
  document.querySelector("meta[name=theme-color]")?.setAttribute("content", dark ? "#000000" : "#fafafa");
}

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  return () => window.removeEventListener("storage", callback);
}

function getSnapshot(): Theme {
  const v = window.localStorage.getItem("theme");
  return v === "light" || v === "dark" || v === "system" ? v : "system";
}

function getServerSnapshot(): Theme {
  return "system";
}

const LABEL: Record<Theme, string> = {
  light: "Light",
  dark: "Dark",
  system: "System",
};

const ICON: Record<Theme, string> = {
  light: "\u2600",
  dark: "\u263D",
  system: "\u25D0",
};

export function ThemeToggle({ className }: { className?: string }) {
  const theme = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getServerSnapshot,
  );

  function cycle() {
    const next = ORDER[(ORDER.indexOf(theme) + 1) % ORDER.length];
    applyTheme(next);
    if (next === "system") {
      window.localStorage.removeItem("theme");
    } else {
      window.localStorage.setItem("theme", next);
    }
    // storage event doesn't fire in the same tab; dispatch manually so
    // useSyncExternalStore subscribers re-read.
    window.dispatchEvent(new StorageEvent("storage"));
  }

  return (
    <button
      type="button"
      onClick={cycle}
      aria-label={`Theme: ${LABEL[theme]}. Click to change.`}
      title={`Theme: ${LABEL[theme]}`}
      className={clsx(
        "inline-flex h-11 w-11 sm:h-9 sm:w-9 items-center justify-center rounded-md border border-line bg-surface-card text-sm text-ink-muted transition-colors hover:bg-surface-inset focus-visible:outline-2 focus-visible:outline-accent",
        className,
      )}
    >
      <span aria-hidden>{ICON[theme]}</span>
    </button>
  );
}
