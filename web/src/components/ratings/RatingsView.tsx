"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import type { PeriodMeta, Rating } from "@/lib/v5";
import TeamLogo from "@/components/TeamLogo";

type Sort = "overall" | "offense" | "defense";

const fields: Record<Sort, keyof Rating> = {
  overall: "overallRating",
  offense: "offenseRating",
  defense: "defenseRating",
};

interface RatingsViewProps {
  ratings: Rating[];
  periodMeta: PeriodMeta;
  season: number;
  initialSort?: Sort;
  initialQuery?: string;
}

export function RatingsView({
  ratings,
  periodMeta,
  season,
  initialSort = "overall",
  initialQuery = "",
}: RatingsViewProps) {
  const [sort, setSort] = useState<Sort>(initialSort);
  const [query, setQuery] = useState(initialQuery);

  // rank computed pre-filter so search doesn't renumber
  const ranked = useMemo(() => {
    return [...ratings]
      .sort((a, b) => Number(b[fields[sort]]) - Number(a[fields[sort]]))
      .map((rating, i) => ({ rating, rank: i + 1 }));
  }, [ratings, sort]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return ranked;
    return ranked.filter(({ rating }) =>
      rating.team.toLowerCase().includes(q),
    );
  }, [ranked, query]);

  return (
    <div className="space-y-4">
      {/* Search and Sort Toolbar */}
      <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between">
        {/* Search input with 1-tap clear button */}
        <div className="relative min-w-0 flex-1 max-w-md">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-ink-faint">
            <svg
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </div>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search teams..."
            aria-label="Search teams"
            className="w-full rounded-lg border border-line bg-surface-card py-2 pr-8 pl-9 text-base text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none sm:text-sm [&::-webkit-search-cancel-button]:hidden"
          />
          {query.length > 0 && (
            <button
              type="button"
              onClick={() => setQuery("")}
              aria-label="Clear search"
              className="absolute inset-y-0 right-0 flex items-center pr-2.5 text-ink-faint hover:text-ink"
            >
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
          )}
        </div>

        {/* Sort Pill Controls */}
        <div className="flex items-center gap-1.5 self-start sm:self-auto">
          <span className="text-xs font-medium text-ink-faint sm:hidden">Sort:</span>
          <div className="grid grid-cols-3 rounded-lg border border-line bg-surface-inset p-0.5 text-xs">
            {(["overall", "offense", "defense"] as const).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setSort(s)}
                className={clsx(
                  "rounded-md px-3 py-1.5 font-medium capitalize transition-all",
                  sort === s
                    ? "bg-surface-card font-semibold text-ink shadow-2xs"
                    : "text-ink-muted hover:text-ink",
                )}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Empty State */}
      {ratings.length === 0 ? (
        <p role="status" className="rounded-xl border border-line bg-surface-card p-5 text-ink-muted">
          No certified ratings published for the {season} season yet.
        </p>
      ) : visible.length === 0 ? (
        <div role="status" className="rounded-xl border border-line bg-surface-card p-6 text-center text-ink-muted">
          <p>No teams match &ldquo;{query}&rdquo;.</p>
          <button
            type="button"
            onClick={() => setQuery("")}
            className="mt-2 text-xs font-semibold text-accent-ink hover:underline"
          >
            Clear search
          </button>
        </div>
      ) : (
        <>
          {/* Mobile Card List (< sm) - No horizontal scroll! */}
          <ul className="space-y-2 sm:hidden" aria-label="Team ratings list">
            {visible.map(({ rating, rank }) => (
              <li
                key={rating.team}
                className="rounded-xl border border-line bg-surface-card p-3 shadow-2xs transition-colors hover:border-line-strong"
              >
                {/* Top Row: Rank + Logo + Team Name on Left, Overall on Right */}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <span
                      className={clsx(
                        "flex h-5 w-6 shrink-0 items-center justify-center rounded font-mono text-[11px] font-bold",
                        rank <= 10
                          ? "bg-accent-soft text-accent-ink"
                          : "bg-surface-inset text-ink-muted",
                      )}
                    >
                      {rank}
                    </span>
                    <TeamLogo name={rating.team} px={20} />
                    <span className="truncate text-sm font-semibold text-ink">
                      {rating.team}
                    </span>
                  </div>
                  <div className="shrink-0 text-right">
                    <span className="font-mono text-base font-bold tabular-nums text-ink">
                      {rating.overallRating >= 0 ? `+${rating.overallRating.toFixed(2)}` : rating.overallRating.toFixed(2)}
                    </span>
                  </div>
                </div>

                {/* Bottom Row: Uncertainty on Left, Offense & Defense Chips on Right */}
                <div className="mt-2 flex items-center justify-between border-t border-line/40 pt-2 text-xs">
                  <span className="font-mono text-[11px] text-ink-faint">
                    ±{Math.sqrt(Math.max(0, rating.overallVariance)).toFixed(2)}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <span className="rounded bg-surface-inset px-2 py-0.5 font-mono text-[11px] text-ink-muted">
                      <span className="text-ink-faint">Off</span>{" "}
                      {rating.offenseRating >= 0 ? `+${rating.offenseRating.toFixed(2)}` : rating.offenseRating.toFixed(2)}
                    </span>
                    <span className="rounded bg-surface-inset px-2 py-0.5 font-mono text-[11px] text-ink-muted">
                      <span className="text-ink-faint">Def</span>{" "}
                      {rating.defenseRating >= 0 ? `+${rating.defenseRating.toFixed(2)}` : rating.defenseRating.toFixed(2)}
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ul>

          {/* Desktop Table (sm:) */}
          <div className="hidden sm:block overflow-hidden rounded-xl border border-line bg-surface-card shadow-sm">
            <table className="w-full text-sm tabular-nums">
              <caption className="sr-only">
                {season} {periodMeta.label} V5 team ratings
              </caption>
              <thead className="border-b border-line bg-surface-inset text-xs uppercase tracking-wide text-ink-faint">
                <tr>
                  <th scope="col" className="w-12 px-3 py-3 text-center">#</th>
                  <th scope="col" className="px-4 py-3 text-left">Team</th>
                  <th scope="col" className="px-3 py-3 text-right">Overall</th>
                  <th scope="col" className="px-3 py-3 text-right">Offense</th>
                  <th scope="col" className="px-3 py-3 text-right">Defense</th>
                  <th scope="col" className="px-4 py-3 text-right">Uncertainty</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60">
                {visible.map(({ rating, rank }) => (
                  <tr key={rating.team} className="transition-colors hover:bg-surface-inset/50">
                    <td className="px-3 py-3 text-center font-mono text-xs text-ink-faint">
                      {rank}
                    </td>
                    <th scope="row" className="px-4 py-3 text-left font-semibold text-ink">
                      <div className="flex items-center gap-2.5">
                        <TeamLogo name={rating.team} px={20} />
                        <span>{rating.team}</span>
                      </div>
                    </th>
                    <td className="px-3 py-3 text-right font-mono font-bold text-ink">
                      {rating.overallRating >= 0 ? `+${rating.overallRating.toFixed(2)}` : rating.overallRating.toFixed(2)}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-ink-muted">
                      {rating.offenseRating >= 0 ? `+${rating.offenseRating.toFixed(2)}` : rating.offenseRating.toFixed(2)}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-ink-muted">
                      {rating.defenseRating >= 0 ? `+${rating.defenseRating.toFixed(2)}` : rating.defenseRating.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-ink-faint">
                      ±{Math.sqrt(Math.max(0, rating.overallVariance)).toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
