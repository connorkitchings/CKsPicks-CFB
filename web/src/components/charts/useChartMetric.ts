"use client";

import { replaceSearchParams } from "@/lib/url-state";
import { usePathname, useSearchParams } from "next/navigation";

/** Client-only metric switches share a reloadable URL without fetching the same chart data again. */
export function useChartMetric<T extends string>(initial: T, allowed: readonly T[]): [T, (value: T) => void] {
  const pathname = usePathname();
  const params = useSearchParams();
  const raw = params.get("metric");
  const metric = allowed.includes(raw as T) ? raw as T : initial;
  return [metric, (value) => {
    replaceSearchParams(pathname, (next) => next.set("metric", value));
  }];
}
