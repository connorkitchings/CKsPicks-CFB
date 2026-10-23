"use client";

import { useSyncExternalStore } from "react";

const QUERY = "(max-width: 639px)";
const subscribe = (notify: () => void) => {
  const media = window.matchMedia(QUERY);
  media.addEventListener("change", notify);
  return () => media.removeEventListener("change", notify);
};

/** True below the 640px breakpoint. The server and hydration render `server` (default false) so initial markup stays stable. */
export function useIsPhone(server = false): boolean {
  return useSyncExternalStore(subscribe, () => window.matchMedia(QUERY).matches, () => server);
}
