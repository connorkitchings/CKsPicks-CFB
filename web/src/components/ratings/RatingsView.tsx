"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import clsx from "clsx";
import type { PeriodMeta, Rating } from "@/lib/rating-periods";
import {
  buildConferenceMap,
  conferenceOptions,
  matchesTeamConference,
  type ConferenceFilter,
  type RosterRow,
} from "@/lib/conferences";
import {
  bestFirstDirection,
  isRatingsSort,
  rankSosByTeam,
  RATINGS_SORTS,
  type RatingsSort,
  type SortDirection,
  type SosRanks,
} from "@/lib/sos-rank";
import { RankChip } from "@/components/ui/RankChip";
import { RatingsFilterSheet } from "./RatingsFilterSheet";
import { MobileStickyBar } from "@/components/ui/MobileStickyBar";
import { useIsPhone } from "@/lib/use-is-phone";
import TeamLogo from "@/components/TeamLogo";
import { Card } from "@/components/ui/Card";
import { Notice } from "@/components/ui/Notice";
import { SearchField } from "@/components/ui/SearchField";
import { SummaryLine, summaryText } from "@/components/ui/SummaryLine";
import { teamHref } from "@/lib/teams";

/** The fields this view renders; the page maps full ratings down to these before they reach the client. */
export type RatingRow = Pick<
  Rating,
  | "team"
  | "overallRating"
  | "offenseRating"
  | "defenseRating"
  | "wins"
  | "losses"
  | "sosPlayedAverage"
  | "sosRemainingAverage"
  | "sosFullAverage"
  | "sor"
  | "sorRank"
>;

type ScoreSort = "overall" | "offense" | "defense";
const scoreSorts: readonly ScoreSort[] = ["overall", "offense", "defense"];
const scoreFields = { overall: "overallRating", offense: "offenseRating", defense: "defenseRating" } as const;
const sosRankField = { sos_played: "played", sos_remaining: "remaining", sos_full: "full" } as const;
const sortLabels: Record<RatingsSort, string> = {
  overall: "Overall",
  offense: "Offense",
  defense: "Defense",
  sor: "SOR",
  sos_played: "SOS Played",
  sos_remaining: "SOS Remaining",
  sos_full: "SOS Full",
};
const tooltips = {
  record: "Record against FBS opponents the period rates; FCS games are excluded.",
  sor: "Strength of record rank: 1 is the strongest résumé.",
  sos: "Schedule difficulty rank among FBS teams (1 is hardest), measured against an average FBS team.",
};

const DASH = "—";
const isNumber = (value: number | null | undefined): value is number => typeof value === "number" && Number.isFinite(value);
const isScoreSort = (sort: RatingsSort): sort is ScoreSort => sort === "overall" || sort === "offense" || sort === "defense";

const ratingText = (value: number) => `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
const oneDecimal = (value: number | null | undefined) => (isNumber(value) ? value.toFixed(1) : DASH);
const rankText = (rank: number | null | undefined) => (isNumber(rank) ? `#${rank}` : DASH);
/** Hover text for a rank cell: the raw value behind the rank. Null values get no title. */
const valueTitle = (label: string, value: number | null | undefined) => (isNumber(value) ? `${label} ${oneDecimal(value)}` : undefined);
const recordText = ({ wins, losses }: RatingRow) => (isNumber(wins) && isNumber(losses) ? `${wins}–${losses}` : DASH);
const sortedClass = (active: boolean) => (active ? "bg-accent-soft font-bold text-ink" : "text-ink-muted");

/** SOS is shown for the average FBS team only; the elite-reference SOS is stored but not displayed. */
function sosValues(rating: RatingRow) {
  return { played: rating.sosPlayedAverage, remaining: rating.sosRemainingAverage, full: rating.sosFullAverage };
}

/** The SOR or SOS rank a team holds; null for the rating sorts and for a null value. */
function rankFor(rating: RatingRow, sort: RatingsSort, sosRanks: Map<string, SosRanks>): number | null {
  if (sort === "sor") return isNumber(rating.sorRank) ? rating.sorRank : null;
  if (isScoreSort(sort)) return null;
  return sosRanks.get(rating.team)?.[sosRankField[sort]] ?? null;
}

/** The value a row is ordered by. Rank sorts order by rank, so rank 1 comes first in the ascending direction. */
function sortKey(rating: RatingRow, sort: RatingsSort, sosRanks: Map<string, SosRanks>): number | null {
  return isScoreSort(sort) ? rating[scoreFields[sort]] : rankFor(rating, sort, sosRanks);
}

/** Orders by key in the given direction; rows with no key sort last whichever way the direction runs. */
function compareRows(a: number | null, b: number | null, direction: SortDirection): number {
  if (a === null || b === null) return Number(a === null) - Number(b === null);
  return direction === "desc" ? b - a : a - b;
}

function primaryText(rating: RatingRow, sort: RatingsSort, sosRanks: Map<string, SosRanks>) {
  return isScoreSort(sort) ? ratingText(rating[scoreFields[sort]]) : rankText(rankFor(rating, sort, sosRanks));
}

/**
 * The four phone-card stat cells. The column the card is sorted by lives in the primary slot, so
 * Overall takes its cell; SOS Remaining and SOS Full sorts keep the played-SOS cell.
 */
function cardStats(rating: RatingRow, sort: RatingsSort, sosRanks: Map<string, SosRanks>) {
  const overall = { label: "OVR", title: "Overall rating", value: ratingText(rating.overallRating) };
  const cells = {
    offense: { label: "OFF", title: "Offense rating", value: ratingText(rating.offenseRating) },
    defense: { label: "DEF", title: "Defense rating", value: ratingText(rating.defenseRating) },
    sor: { label: "SOR", title: "Strength of record rank", value: rankText(rankFor(rating, "sor", sosRanks)) },
    sos: { label: "SOS", title: "Strength of schedule played", value: rankText(sosRanks.get(rating.team)?.played) },
  };
  const swapped = sort === "sos_played" ? "sos" : sort === "offense" || sort === "defense" || sort === "sor" ? sort : null;
  return [cells.offense, cells.defense, cells.sor, cells.sos].map((cell) => (swapped && cell === cells[swapped] ? overall : cell));
}

function RankPill({ rank, cohort }: { rank: number | null | undefined; cohort: number }) {
  return isNumber(rank) ? <RankChip rank={rank} total={cohort} /> : <>{DASH}</>;
}

interface SortHeaderProps {
  column: RatingsSort;
  active: boolean;
  direction: SortDirection;
  onSort: (sort: RatingsSort) => void;
  title?: string;
  /** Center the header and button (rank columns); numeric columns stay right-aligned. */
  center?: boolean;
}

/** A sortable column header. The button is the keyboard target; `aria-sort` reports the order of the rows. */
function SortHeader({ column, active, direction, onSort, title, center }: SortHeaderProps) {
  const label = sortLabels[column];
  const indicator = direction === "desc" ? "↓" : "↑";
  return (
    <th
      scope="col"
      title={title}
      aria-sort={active ? (direction === "desc" ? "descending" : "ascending") : "none"}
      className={clsx("px-2 py-3 whitespace-nowrap", center ? "text-center" : "text-right", active && "bg-accent-soft text-accent-ink")}
    >
      <button
        type="button"
        aria-label={`Sort by ${label}`}
        onClick={() => onSort(column)}
        className={clsx("inline-flex min-h-9 items-center gap-1 rounded-md font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent", center ? "justify-center" : "justify-end")}
      >
        {label}
        <span aria-hidden="true" className="w-3 text-center text-xs">{active ? indicator : ""}</span>
      </button>
    </th>
  );
}

interface RatingsViewProps {
  ratings: RatingRow[];
  roster?: RosterRow[];
  periodMeta: Pick<PeriodMeta, "label">;
  period: string;
  timeline: Pick<PeriodMeta, "id" | "label">[];
  season: number;
  initialSort: RatingsSort;
  initialDirection: SortDirection;
  initialQuery?: string;
  initialConference?: ConferenceFilter;
}

export function RatingsView({
  ratings,
  roster = [],
  periodMeta,
  period,
  timeline,
  season,
  initialSort,
  initialDirection,
  initialQuery = "",
  initialConference = "all",
}: RatingsViewProps) {
  const router = useRouter();
  const mobile = useIsPhone();
  const [sort, setSort] = useState<RatingsSort>(initialSort);
  const [direction, setDirection] = useState<SortDirection>(initialDirection);
  const [query, setQuery] = useState(initialQuery);
  const [conference, setConference] = useState<ConferenceFilter>(initialConference);
  const conferenceMap = useMemo(() => buildConferenceMap(roster), [roster]);
  const conferences = useMemo(() => conferenceOptions(roster), [roster]);
  const hasResume = ratings.some((rating) => (
    isNumber(rating.wins) || isNumber(rating.sor) || isNumber(rating.sorRank) || isNumber(rating.sosFullAverage)
  ));

  // SOS ranks come from every team of the period, so searching never changes a team's rank.
  const sosRanks = useMemo(() => rankSosByTeam(ratings), [ratings]);
  // Rank before filtering so searching keeps a team's national rank for the sort.
  const ranked = useMemo(() => ratings
    .map((rating) => ({ rating, key: sortKey(rating, sort, sosRanks) }))
    .sort((a, b) => compareRows(a.key, b.key, direction))
    .map(({ rating }, i) => ({ rating, position: i + 1 })), [ratings, sort, direction, sosRanks]);
  const visible = useMemo(() => {
    const search = query.trim().toLowerCase();
    return ranked.filter(({ rating }) => {
      if (conference !== "all" && !matchesTeamConference(conference, rating.team, conferenceMap)) return false;
      return search ? rating.team.toLowerCase().includes(search) : true;
    });
  }, [ranked, query, conference, conferenceMap]);

  /** Picking a new column opens it best-first; picking the active column flips its direction. */
  function chooseSort(next: RatingsSort) {
    if (next === sort) {
      setDirection(direction === "desc" ? "asc" : "desc");
      return;
    }
    setSort(next);
    setDirection(bestFirstDirection(next));
  }

  function onSortSelect(value: string) {
    if (isRatingsSort(value)) chooseSort(value);
  }

  function periodHref(nextPeriod: string) {
    const params = new URLSearchParams({ period: nextPeriod, sort, season: String(season) });
    if (direction !== bestFirstDirection(sort)) params.set("dir", direction);
    if (query.trim()) params.set("q", query.trim().slice(0, 80));
    if (conference !== "all") params.set("conf", conference);
    return `/ratings?${params.toString()}`;
  }

  const latestPeriod = timeline[timeline.length - 1]?.id ?? period;
  const periodLabel = timeline.find((entry) => entry.id === period)?.label ?? periodMeta.label;
  const conferenceLabel = conference === "all" ? "All FBS" : conference === "p4" ? "Power Four + Notre Dame" : conference;
  const filtersActive = conference !== "all" || sort !== "overall" || period !== latestPeriod;
  const summary = summaryText(conferenceLabel, sortLabels[sort], periodLabel, "V5");

  const periodSelect = timeline.length > 0 && (
    <div>
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
  );
  const conferenceSelect = conferences.length > 0 && (
    <div>
      <label htmlFor="rating-conference" className="mb-1 block text-sm font-semibold text-ink sm:sr-only">Filter by conference</label>
      <select
        id="rating-conference"
        data-testid="conference-filter"
        aria-label="Filter by conference"
        value={conference}
        onChange={(event) => setConference(event.target.value)}
        className="min-h-11 w-full min-w-0 rounded-lg border border-line bg-surface-card px-3 text-base text-ink sm:min-h-9 sm:w-auto sm:text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        <option value="all">All FBS</option>
        <option value="p4">Power Four + Notre Dame</option>
        {conferences.map((conf) => (
          <option key={conf} value={conf}>{conf}</option>
        ))}
      </select>
    </div>
  );
  const sortSelect = (
    <div>
      <label htmlFor="rating-sort" className="mb-1 block text-sm font-semibold text-ink">Sort by</label>
      <select
        id="rating-sort"
        value={sort}
        onChange={(event) => onSortSelect(event.target.value)}
        className="min-h-11 w-full min-w-0 rounded-lg border border-line bg-surface-card px-3 text-base text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        {RATINGS_SORTS.map((value) => <option key={value} value={value}>{sortLabels[value]}</option>)}
      </select>
    </div>
  );

  // One control tree: on phones the period, conference and sort selects live in the Filters sheet;
  // from 640px the timeline links and the conference select sit inline, as before.
  return (
    <div className="flex flex-col gap-2 sm:gap-4">
      {!mobile && timeline.length > 0 && (
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
      )}

      {/* Phones: this row is the sticky bar (search + Filters). */}
      <MobileStickyBar data-testid="ratings-bar" className="flex items-center gap-2 sm:justify-between">
        <SearchField
          id="rating-search"
          label="Search teams"
          value={query}
          onChange={setQuery}
          placeholder="Search teams…"
          clearLabel="Clear search"
          className="min-w-0 flex-1 sm:max-w-md"
        />
        <RatingsFilterSheet mobile={mobile} active={filtersActive}>
          {mobile && periodSelect}
          {mobile && conferenceSelect}
          {mobile && sortSelect}
        </RatingsFilterSheet>
        {!mobile && conferenceSelect && <div className="hidden sm:block">{conferenceSelect}</div>}
      </MobileStickyBar>

      <SummaryLine parts={[summary]} className="text-xs text-ink-muted sm:hidden" data-testid="ratings-summary" />

      {hasResume && (
        <p className="text-xs text-ink-muted max-sm:order-last">
          SOS ranks schedule difficulty for an average FBS team (1 is hardest). SOR ranks each team’s record against what an <Link href="/model/method#elite-reference" className="font-semibold text-accent-ink hover:underline max-sm:-mx-2.5 max-sm:-my-3 max-sm:inline-flex max-sm:min-h-11 max-sm:min-w-11 max-sm:items-center max-sm:justify-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">elite</Link> team (the average of the top 25 teams) would be expected to do on the same schedule; see the methodology.
        </p>
      )}

      {ratings.length === 0 ? (
        <Notice tone="empty">No certified ratings published for the {season} season yet.</Notice>
      ) : visible.length === 0 ? (
        <Notice tone="empty" className="justify-center p-6 text-center">
          <p>No teams match &ldquo;{query}&rdquo;.</p>
          <button type="button" onClick={() => { setQuery(""); setConference("all"); }} className="mt-2 min-h-11 rounded-lg px-3 text-sm font-semibold text-accent-ink hover:underline focus-visible:outline-2 focus-visible:outline-accent">Clear search</button>
        </Notice>
      ) : (
        <>
          <ul className="space-y-2 sm:hidden" aria-label="Team ratings list">
            {visible.map(({ rating, position }) => (
              <Card as="li" padding="sm" key={rating.team}>
                <div className="flex items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <RankChip aria-label={`National rank ${position}`} rank={null} label={String(position)} prefix="" className="h-6 min-w-6 shrink-0" />
                    <Link href={teamHref(rating.team)} className="flex min-h-11 min-w-0 items-center gap-2 -my-2.5 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
                      <TeamLogo name={rating.team} px={24} />
                      <span className="min-w-0">
                        <span className="block break-words text-sm font-semibold leading-tight text-ink">{rating.team}</span>
                        <span className="block text-xs text-ink-muted" title={tooltips.record}>{recordText(rating)}</span>
                      </span>
                    </Link>
                  </div>
                  <div className="shrink-0 text-right" data-testid="primary-rating">
                    <p className="text-[10px] font-medium uppercase tracking-wide text-ink-muted">{sortLabels[sort]}</p>
                    <p className="font-mono text-lg font-bold tabular-nums text-ink">{primaryText(rating, sort, sosRanks)}</p>
                  </div>
                </div>
                <dl className="mt-2 grid grid-cols-4 gap-1 border-t border-line pt-2">
                  {cardStats(rating, sort, sosRanks).map((cell) => (
                    <div key={cell.label} title={cell.title} aria-label={cell.title} role="group" className="min-w-0 text-center">
                      <dt className="text-[10px] uppercase tracking-wide text-ink-muted">{cell.label}</dt>
                      <dd className="font-mono text-sm font-semibold tabular-nums text-ink">{cell.value}</dd>
                    </div>
                  ))}
                </dl>
              </Card>
            ))}
          </ul>

          <Card padding="none" className="hidden overflow-x-auto sm:block">
            <table className="w-full text-sm tabular-nums">
              <caption className="sr-only">{season} {periodMeta.label} V5 team ratings, ranked by {sortLabels[sort]}</caption>
              <thead className="border-b border-line bg-surface-inset text-xs text-ink-muted">
                <tr>
                  <th scope="col" className="whitespace-nowrap px-2 py-3 text-center">Rank</th>
                  <th scope="col" className="px-2 py-3 text-left">Team</th>
                  {scoreSorts.map((column) => (
                    <SortHeader key={column} column={column} active={sort === column} direction={direction} onSort={chooseSort} center />
                  ))}
                  <th scope="col" title={tooltips.record} className="px-2 py-3 text-center whitespace-nowrap">FBS W-L</th>
                  <SortHeader column="sor" active={sort === "sor"} direction={direction} onSort={chooseSort} title={tooltips.sor} center />
                  <SortHeader column="sos_played" active={sort === "sos_played"} direction={direction} onSort={chooseSort} title={tooltips.sos} center />
                  <SortHeader column="sos_remaining" active={sort === "sos_remaining"} direction={direction} onSort={chooseSort} title={tooltips.sos} center />
                  <SortHeader column="sos_full" active={sort === "sos_full"} direction={direction} onSort={chooseSort} title={tooltips.sos} center />
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {visible.map(({ rating, position }) => {
                  const sos = sosValues(rating);
                  const teamRanks = sosRanks.get(rating.team);
                  return (
                    <tr key={rating.team}>
                      <td className="px-2 py-3 text-center font-mono text-xs text-ink-muted">
                        {/* Neutral on purpose: the color scale marks the SOR and SOS rank columns, not the position. */}
                        <RankChip rank={null} label={String(position)} prefix="" />
                      </td>
                      <th scope="row" className="px-2 py-3 text-left font-semibold text-ink">
                        <Link href={teamHref(rating.team)} className="flex items-center gap-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"><TeamLogo name={rating.team} px={20} /><span>{rating.team}</span></Link>
                      </th>
                      {scoreSorts.map((column) => (
                        <td key={column} className={clsx("px-2 py-3 text-center font-mono", sortedClass(sort === column))}>{ratingText(rating[scoreFields[column]])}</td>
                      ))}
                      <td className="whitespace-nowrap px-2 py-3 text-center font-mono text-ink-muted">{recordText(rating)}</td>
                      <td title={valueTitle("SOR", rating.sor)} className={clsx("whitespace-nowrap px-2 py-3 text-center font-mono", sortedClass(sort === "sor"))}><RankPill rank={rankFor(rating, "sor", sosRanks)} cohort={ratings.length} /></td>
                      <td title={valueTitle("SOS Played", sos.played)} className={clsx("whitespace-nowrap px-2 py-3 text-center font-mono", sortedClass(sort === "sos_played"))}><RankPill rank={teamRanks?.played} cohort={ratings.length} /></td>
                      <td title={valueTitle("SOS Remaining", sos.remaining)} className={clsx("whitespace-nowrap px-2 py-3 text-center font-mono", sortedClass(sort === "sos_remaining"))}><RankPill rank={teamRanks?.remaining} cohort={ratings.length} /></td>
                      <td title={valueTitle("SOS Full", sos.full)} className={clsx("whitespace-nowrap px-2 py-3 text-center font-mono", sortedClass(sort === "sos_full"))}><RankPill rank={teamRanks?.full} cohort={ratings.length} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}
