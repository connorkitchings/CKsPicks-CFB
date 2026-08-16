"use client";

import { useRouter, useSearchParams } from "next/navigation";
import clsx from "clsx";

/**
 * Prev / next / dropdown navigator over the available weeks for the active
 * season. Selecting or arrowing swaps the `?season=&week=` query params,
 * which the server component in app/page.tsx reads to fetch the right slice.
 *
 * Anchor-style navigation (full RSC refresh) is preferred over client state
 * so URLs stay shareable and ISR caches each combination.
 */
export function WeekNav({
  season,
  week,
  weeks,
}: {
  season: number;
  week: number;
  weeks: number[];
}) {
  const router = useRouter();
  const params = useSearchParams();

  if (weeks.length === 0) return null;

  const idx = weeks.indexOf(week);
  const safeIdx = idx === -1 ? weeks.length - 1 : idx;
  const prev = safeIdx > 0 ? weeks[safeIdx - 1] : null;
  const next = safeIdx < weeks.length - 1 ? weeks[safeIdx + 1] : null;

  function hrefFor(w: number): string {
    const q = new URLSearchParams(params.toString());
    q.set("season", String(season));
    q.set("week", String(w));
    return `/?${q.toString()}`;
  }

  function onSelect(e: React.ChangeEvent<HTMLSelectElement>) {
    const w = Number(e.target.value);
    if (Number.isFinite(w)) router.push(hrefFor(w));
  }

  const arrow =
    "inline-flex h-9 w-9 items-center justify-center rounded-md border border-line bg-surface-card text-base text-ink-muted transition-colors hover:bg-surface-inset disabled:cursor-not-allowed disabled:opacity-40";

  return (
    <nav
      aria-label="Week navigation"
      className="flex items-center justify-between gap-2 rounded-xl border border-line bg-surface-card p-2 shadow-sm"
    >
      <a
        href={prev !== null ? hrefFor(prev) : undefined}
        aria-label="Previous week"
        className={clsx(arrow, prev === null && "pointer-events-none opacity-40")}
      >
        {/* left arrow */}
        <span aria-hidden>&larr;</span>
      </a>

      <div className="flex items-center gap-2 text-sm">
        <label htmlFor="week-select" className="sr-only">
          Week
        </label>
        <select
          id="week-select"
          value={week}
          onChange={onSelect}
          className="rounded-md border border-line bg-surface-card px-2 py-1 text-sm font-medium text-ink focus:outline-none focus:ring-2 focus:ring-accent"
        >
          {weeks.map((w) => (
            <option key={w} value={w}>
              Week {w}
            </option>
          ))}
        </select>
        <span className="text-xs tabular-nums text-ink-faint">
          {safeIdx + 1} / {weeks.length}
        </span>
      </div>

      <a
        href={next !== null ? hrefFor(next) : undefined}
        aria-label="Next week"
        className={clsx(arrow, next === null && "pointer-events-none opacity-40")}
      >
        <span aria-hidden>&rarr;</span>
      </a>
    </nav>
  );
}
