"use client";

import { useSyncExternalStore } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { withChartState } from "@/lib/chart-config";

export type ChartSelectGroup = { id: string; label: string; options: { href: string; label: string; shortLabel?: string }[] };

const NARROW = "(max-width: 359px)";
const subscribeNarrow = (notify: () => void) => {
  const media = window.matchMedia(NARROW);
  media.addEventListener("change", notify);
  return () => media.removeEventListener("change", notify);
};
/** True below 360px; false on the server and during hydration so the first markup is stable. */
const useIsNarrow = () => useSyncExternalStore(subscribeNarrow, () => window.matchMedia(NARROW).matches, () => false);

/**
 * Phone chart picker: a native select (OS picker on iOS and Android) that navigates like
 * the desktop `ChartLink`s: same hrefs, the `team=` highlight carried over, one history entry.
 */
export function ChartSelect({ groups, currentHref }: { groups: ChartSelectGroup[]; currentHref: string }) {
  const router = useRouter();
  const params = useSearchParams();
  const narrow = useIsNarrow();
  return (
    <>
      <label htmlFor="chart-select" className="sr-only">Chart type</label>
      <select
        id="chart-select"
        data-testid="chart-select"
        value={currentHref}
        onChange={(event) => router.push(withChartState(event.target.value, params.toString()))}
        className="block min-h-11 w-full rounded-lg border border-line bg-surface-card px-3 text-base font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        {groups.map((group) => (
          <optgroup key={group.id} label={group.label}>
            {group.options.map((option) => <option key={option.href} value={option.href}>{narrow ? option.shortLabel ?? option.label : option.label}</option>)}
          </optgroup>
        ))}
      </select>
    </>
  );
}
