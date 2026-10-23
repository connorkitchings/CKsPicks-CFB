"use client";

import { useEffect } from "react";

/** Flags the document once React has hydrated so e2e tests can wait for interactivity. */
export function HydrationMarker() {
  useEffect(() => {
    document.documentElement.dataset.hydrated = "true";
  }, []);
  return null;
}
