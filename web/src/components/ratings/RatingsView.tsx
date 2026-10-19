"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import clsx from "clsx";
import type { PeriodMeta, Rating } from "@/lib/rating-periods";
import TeamLogo from "@/components/TeamLogo";
import { SearchField } from "@/components/ui/SearchField";
import { SegmentedControl } from "@/components/ui/SegmentedControl";

type Sort = "overall" | "offense" | "defense";
const categories = [
  { value: "overall", label: "Overall" },
  { value: "offense", label: "Offense" },
  { value: "defense", label: "Defense" },
] as const;
const fields = {
  overall: "overallRating",
  offense: "offenseRating",
  defense: "defenseRating",
} as const;
const ratingText = (value: number) => `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
const uncertainty = (rating: Rating) => `±${Math.sqrt(Math.max(0, rating.overallVariance)).toFixed(2)}`;

interface RatingsViewProps {
  ratings: Rating[];
  periodMeta: PeriodMeta;
  period: string;
  timeline: PeriodMeta[];
  season: number;
  initialSort?: Sort;
  initialQuery?: string;
}

export function RatingsView({
  ratings,
  periodMeta,
  period,
  timeline,
  season,
  initialSort = "overall",
  initialQuery = "",
}: RatingsViewProps) {
  const router = useRouter();
  const [sort, setSort] = useState<Sort>(initialSort);
  const [query, setQuery] = useState(initialQuery);
  const selectedCategory = categories.find((category) => category.value === sort)!;

  // Rank before filtering so searching keeps a team's national category rank.
  const ranked = useMemo(() => [...ratings]
    .sort((a, b) => b[fields[sort]] - a[fields[sort]])
    .map((rating, i) => ({ rating, rank: i + 1 })), [ratings, sort]);
  const visible = useMemo(() => {
    const search = query.trim().toLowerCase();
    return search ? ranked.filter(({ rating }) => rating.team.toLowerCase().includes(search)) : ranked;
  }, [ranked, query]);

  function periodHref(nextPeriod: string) {
    const params = new URLSearchParams({ period: nextPeriod, sort, season: String(season) });
    if (query.trim()) params.set("q", query.trim().slice(0, 80));
    return `/ratings?${params.toString()}`;
  }

  return (
    <div className="space-y-4">
      {timeline.length > 0 && (
        <>
          <div className="sm:hidden">
            <label htmlFor="rating-period" className="mb-1 block text-sm font-semibold text-ink">Rating period</label>
            <select
              id="rating-period"
              value={period}
              onChange={(event) => router.push(periodHref(event.target.value), { scroll: false })}
              className="min-h-11 w-full min-w-0 rounded-lg border border-line bg-surface-card px-3 text-base text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              {timeline.map((entry) => <option key={entry.id} value={entry.id}>{entry.label}</option>)}
            </select>
          </div>
          <nav aria-label="Ratings timeline" className="hidden flex-wrap gap-2 sm:flex">
            {timeline.map((entry) => <Link
              key={entry.id}
              href={periodHref(entry.id)}
              scroll={false}
              aria-current={entry.id === period ? "page" : undefined}
              className={clsx(
                "inline-flex min-h-11 items-center rounded-lg border px-3 py-2 text-sm sm:min-h-9 sm:py-1.5 font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                entry.id === period ? "border-accent bg-accent-soft text-accent-ink" : "border-line bg-surface-card text-ink-muted hover:bg-surface-inset",
              )}
            >{entry.label}</Link>)}
          </nav>
        </>
      )}

      <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between">
        <SearchField
          id="rating-search"
          label="Search teams"
          value={query}
          onChange={setQuery}
          placeholder="Search teams…"
          clearLabel="Clear search"
          className="w-full sm:max-w-md"
        />
        <SegmentedControl
          label="Rating category"
          value={sort}
          onChange={setSort}
          options={categories}
          fill
          className="sm:shrink-0"
        />
      </div>

      {ratings.length === 0 ? (
        <p role="status" className="rounded-xl border border-line bg-surface-card p-5 text-sm text-ink-muted">No certified ratings published for the {season} season yet.</p>
      ) : visible.length === 0 ? (
        <div role="status" className="rounded-xl border border-line bg-surface-card p-6 text-center text-sm text-ink-muted">
          <p>No teams match &ldquo;{query}&rdquo;.</p>
          <button type="button" onClick={() => setQuery("")} className="mt-2 min-h-11 rounded-lg px-3 text-sm font-semibold text-accent-ink hover:underline focus-visible:outline-2 focus-visible:outline-accent">Clear search</button>
        </div>
      ) : (
        <>
          <ul className="space-y-2 sm:hidden" aria-label="Team ratings list">
            {visible.map(({ rating, rank }) => (
              <li key={rating.team} className="rounded-xl border border-line bg-surface-card p-3 shadow-2xs">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-start gap-2">
                    <span aria-label={`National rank ${rank}`} className="flex h-6 min-w-6 shrink-0 items-center justify-center rounded bg-accent-soft px-1 font-mono text-xs font-bold text-accent-ink">{rank}</span>
                    <TeamLogo name={rating.team} px={24} />
                    <span className="min-w-0 break-words text-sm font-semibold text-ink">{rating.team}</span>
                  </div>
                  <div className="shrink-0 text-right" data-testid="primary-rating">
                    <p className="text-xs font-medium text-ink-muted">{selectedCategory.label}</p>
                    <p className="font-mono text-lg font-bold tabular-nums text-ink">{ratingText(rating[fields[sort]])}</p>
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 border-t border-line pt-2 text-xs text-ink-muted">
                  {categories.filter((category) => category.value !== sort).map((category) => <span key={category.value}>{category.label} <span className="font-mono">{ratingText(rating[fields[category.value]])}</span></span>)}
                  <span className="w-full">Overall uncertainty <span className="font-mono">{uncertainty(rating)}</span></span>
                </div>
              </li>
            ))}
          </ul>

          <div className="hidden overflow-hidden rounded-xl border border-line bg-surface-card sm:block">
            <table className="w-full text-sm tabular-nums">
              <caption className="sr-only">{season} {periodMeta.label} V5 team ratings, ranked by {selectedCategory.label.toLowerCase()}</caption>
              <thead className="border-b border-line bg-surface-inset text-xs text-ink-muted">
                <tr>
                  <th scope="col" className="px-2 py-3 text-center">#</th>
                  <th scope="col" className="px-2 py-3 text-left">Team</th>
                  {categories.map((category) => <th key={category.value} scope="col" aria-sort={sort === category.value ? "descending" : undefined} className={clsx("px-2 py-3 text-right", sort === category.value && "bg-accent-soft text-accent-ink")}>{category.label}</th>)}
                  <th scope="col" className="px-2 py-3 text-right">Overall uncertainty</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {visible.map(({ rating, rank }) => (
                  <tr key={rating.team}>
                    <td className="px-2 py-3 text-center font-mono text-xs text-ink-muted">{rank}</td>
                    <th scope="row" className="px-2 py-3 text-left font-semibold text-ink">
                      <div className="flex items-center gap-2"><TeamLogo name={rating.team} px={20} /><span>{rating.team}</span></div>
                    </th>
                    {categories.map((category) => <td key={category.value} className={clsx("px-2 py-3 text-right font-mono", sort === category.value ? "bg-accent-soft font-bold text-ink" : "text-ink-muted")}>{ratingText(rating[fields[category.value]])}</td>)}
                    <td className="px-2 py-3 text-right font-mono text-ink-muted">{uncertainty(rating)}</td>
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
