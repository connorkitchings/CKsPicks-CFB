"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Fragment, useMemo, useState } from "react";
import clsx from "clsx";
import type { PeriodMeta, Rating } from "@/lib/rating-periods";
import TeamLogo from "@/components/TeamLogo";
import { SearchField } from "@/components/ui/SearchField";
import { SegmentedControl } from "@/components/ui/SegmentedControl";

type Sort = "overall" | "offense" | "defense" | "sor" | "sos";

const sorts: readonly Sort[] = ["overall", "offense", "defense", "sor", "sos"];
/** Unknown or removed `?sort=` values (such as the retired `waa`) fall back to overall. */
const isSort = (value: string): value is Sort => (sorts as readonly string[]).includes(value);

const categories = [
  { value: "overall", label: "Overall" },
  { value: "offense", label: "Offense" },
  { value: "defense", label: "Defense" },
] as const;
const resumeSorts = [
  { value: "sor", label: "SOR" },
  { value: "sos", label: "SOS" },
] as const;
const fields = {
  overall: "overallRating",
  offense: "offenseRating",
  defense: "defenseRating",
} as const;
const sortLabels: Record<Sort, string> = {
  overall: "Overall",
  offense: "Offense",
  defense: "Defense",
  sor: "SOR",
  sos: "SOS full",
};
const tooltips = {
  record: "Record against FBS opponents the period rates; FCS games are excluded.",
  sor: "Strength of record rank: 1 is the strongest résumé. How unlikely an elite team would be to match this record against this schedule.",
  sos: "How often an average FBS team would lose these games, scaled to 100. Higher is a harder schedule.",
};
// Phones need 44px targets; the sm segment size is 30px, so raise its buttons below `sm:` to 36px.
const resumeControlClass = "[&_button]:min-h-11 sm:[&_button]:min-h-9";
const groupLabelClass = "text-xs font-semibold uppercase tracking-wider text-ink-muted";

const DASH = "—";
const ratingText = (value: number) => `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
const sortedClass = (active: boolean) => (active ? "bg-accent-soft font-bold text-ink" : "text-ink-muted");
const sortedHeaderClass = (active: boolean) => clsx("px-2 py-3 text-right whitespace-nowrap", active && "bg-accent-soft text-accent-ink");

const isNumber = (value: number | null | undefined): value is number => typeof value === "number" && Number.isFinite(value);
const oneDecimal = (value: number | null | undefined) => (isNumber(value) ? value.toFixed(1) : DASH);
const rankText = (rating: Rating) => (isNumber(rating.sorRank) ? `#${rating.sorRank}` : DASH);
/** The SOR score is not displayed; it stays available on hover of the rank cell. */
const sorTitle = (rating: Rating) => (isNumber(rating.sor) ? `SOR ${oneDecimal(rating.sor)}` : undefined);
const recordText = ({ wins, losses }: Rating) => (isNumber(wins) && isNumber(losses) ? `${wins}–${losses}` : DASH);

/** SOS is shown for the average FBS team only; the elite-reference SOS is stored but not displayed. */
function sosValues(rating: Rating) {
  return { played: rating.sosPlayedAverage, remaining: rating.sosRemainingAverage, full: rating.sosFullAverage };
}
const sosText = (rating: Rating) => {
  const { played, remaining, full } = sosValues(rating);
  return [played, remaining, full].map(oneDecimal).join(" / ");
};

/**
 * Key a row is ordered by, higher first; null when the row has no value for the sort.
 * SOR ranks 1 first, so its key is the negated rank (ascending rank in a descending order).
 * SOS orders by the average-reference Full value, higher (harder) first.
 */
function sortValue(rating: Rating, sort: Sort): number | null {
  switch (sort) {
    case "sor": return isNumber(rating.sorRank) ? -rating.sorRank : null;
    case "sos": return isNumber(rating.sosFullAverage) ? rating.sosFullAverage : null;
    default: return rating[fields[sort]];
  }
}

/** Descending, with nulls after every value. */
function compareDescendingNullsLast(a: number | null, b: number | null) {
  if (a === null || b === null) return (a === null ? 1 : 0) - (b === null ? 1 : 0);
  return b - a;
}

function primaryText(rating: Rating, sort: Sort) {
  switch (sort) {
    case "sor": return rankText(rating);
    case "sos": return oneDecimal(sosValues(rating).full);
    default: return ratingText(rating[fields[sort]]);
  }
}

interface RatingsViewProps {
  ratings: Rating[];
  periodMeta: PeriodMeta;
  period: string;
  timeline: PeriodMeta[];
  season: number;
  initialSort?: string;
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
  const [sort, setSort] = useState<Sort>(isSort(initialSort) ? initialSort : "overall");
  const [query, setQuery] = useState(initialQuery);
  const hasResume = ratings.some((rating) => (
    isNumber(rating.wins) || isNumber(rating.sor) || isNumber(rating.sorRank) || isNumber(rating.sosFullAverage)
  ));

  // Rank before filtering so searching keeps a team's national rank for the sort.
  const ranked = useMemo(() => [...ratings]
    .map((rating) => ({ rating, value: sortValue(rating, sort) }))
    .sort((a, b) => compareDescendingNullsLast(a.value, b.value))
    .map(({ rating }, i) => ({ rating, rank: i + 1 })), [ratings, sort]);
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

      {hasResume && (
        <div className="space-y-2">
          <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-2">
            <span className={groupLabelClass}>Sort by résumé</span>
            <SegmentedControl
              size="sm"
              label="Résumé sort"
              value={sort}
              onChange={setSort}
              options={resumeSorts}
              fill
              className={resumeControlClass}
            />
          </div>
          <p className="text-xs text-ink-muted">
            SOS is the schedule’s difficulty for an average FBS team. SOR ranks each team’s record against what an <Link href="/methodology#elite-reference" className="font-semibold text-accent-ink hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">elite</Link> team (the average of the top 25 teams) would be expected to do on the same schedule; see the methodology.
          </p>
        </div>
      )}

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
                  <div className="shrink-0 text-right">
                    <div data-testid="primary-rating">
                      <p className="text-xs font-medium text-ink-muted">{sortLabels[sort]}</p>
                      <p className="font-mono text-lg font-bold tabular-nums text-ink">{primaryText(rating, sort)}</p>
                    </div>
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 border-t border-line pt-2 text-xs text-ink-muted">
                  {categories.filter((category) => category.value !== sort).map((category) => (
                    <span key={category.value}>
                      {category.label} <span className="font-mono">{ratingText(rating[fields[category.value]])}</span>
                    </span>
                  ))}
                  <span>FBS W-L <span className="font-mono">{recordText(rating)}</span></span>
                  {sort !== "sor" && <span>SOR <span className="font-mono">{rankText(rating)}</span></span>}
                  {sort !== "sos" && <span>SOS <span className="font-mono">{sosText(rating)}</span> (Played / Remaining / Full)</span>}
                </div>
              </li>
            ))}
          </ul>

          <div className="hidden overflow-x-auto rounded-xl border border-line bg-surface-card sm:block">
            <table className="w-full text-sm tabular-nums">
              <caption className="sr-only">{season} {periodMeta.label} V5 team ratings, ranked by {sortLabels[sort]}</caption>
              <thead className="border-b border-line bg-surface-inset text-xs text-ink-muted">
                <tr>
                  <th scope="col" className="px-2 py-3 text-center">#</th>
                  <th scope="col" className="px-2 py-3 text-left">Team</th>
                  {categories.map((category) => (
                    <Fragment key={category.value}>
                      <th scope="col" aria-sort={sort === category.value ? "descending" : undefined} className={sortedHeaderClass(sort === category.value)}>{category.label}</th>
                    </Fragment>
                  ))}
                  <th scope="col" title={tooltips.record} className="px-2 py-3 text-right whitespace-nowrap">FBS W-L</th>
                  <th scope="col" title={tooltips.sor} aria-sort={sort === "sor" ? "descending" : undefined} className={sortedHeaderClass(sort === "sor")}>SOR</th>
                  <th scope="col" title={tooltips.sos} className="px-2 py-3 text-right whitespace-nowrap">SOS Played</th>
                  <th scope="col" title={tooltips.sos} className="px-2 py-3 text-right whitespace-nowrap">SOS Remaining</th>
                  <th scope="col" title={tooltips.sos} aria-sort={sort === "sos" ? "descending" : undefined} className={sortedHeaderClass(sort === "sos")}>SOS Full</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {visible.map(({ rating, rank }) => {
                  const sos = sosValues(rating);
                  return (
                    <tr key={rating.team}>
                      <td className="px-2 py-3 text-center font-mono text-xs text-ink-muted">{rank}</td>
                      <th scope="row" className="px-2 py-3 text-left font-semibold text-ink">
                        <div className="flex items-center gap-2"><TeamLogo name={rating.team} px={20} /><span>{rating.team}</span></div>
                      </th>
                      {categories.map((category) => (
                        <Fragment key={category.value}>
                          <td className={clsx("px-2 py-3 text-right font-mono", sortedClass(sort === category.value))}>{ratingText(rating[fields[category.value]])}</td>
                        </Fragment>
                      ))}
                      <td className="whitespace-nowrap px-2 py-3 text-right font-mono text-ink-muted">{recordText(rating)}</td>
                      <td title={sorTitle(rating)} className={clsx("whitespace-nowrap px-2 py-3 text-right font-mono", sortedClass(sort === "sor"))}>{rankText(rating)}</td>
                      <td className="whitespace-nowrap px-2 py-3 text-right font-mono text-ink-muted">{oneDecimal(sos.played)}</td>
                      <td className="whitespace-nowrap px-2 py-3 text-right font-mono text-ink-muted">{oneDecimal(sos.remaining)}</td>
                      <td className={clsx("whitespace-nowrap px-2 py-3 text-right font-mono", sortedClass(sort === "sos"))}>{oneDecimal(sos.full)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
