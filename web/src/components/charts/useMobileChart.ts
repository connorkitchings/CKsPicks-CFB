"use client";

import { useSyncExternalStore } from "react";

const QUERY = "(max-width: 639px)";
const subscribe = (notify: () => void) => {
  const media = window.matchMedia(QUERY);
  media.addEventListener("change", notify);
  return () => media.removeEventListener("change", notify);
};

/** Shares the chart breakpoint without changing the server's initial markup. */
export function useMobileChart(): boolean {
  return useSyncExternalStore(subscribe, () => window.matchMedia(QUERY).matches, () => false);
}
