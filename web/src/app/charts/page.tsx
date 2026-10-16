import Link from "next/link";
import clsx from "clsx";
import {
  CHART_TAB_LABELS,
  adjustedPoints,
  adjustedThroughWeeks,
  coerceWeek,
  efficiencyPoints,
  efficiencyThroughWeeks,
  netSuccessBars,
  netSuccessWeeks,
  type AdjustedRow,
  type ChartKind,
  type RosterRow,
  type Side,
  type TeamGameRow,
} from "@/lib/charts";
import { publicationScope } from "@/lib/publication";
import {
  getTeamAdjustedEpa,
  getTeamAdjustedWeeks,
  getTeamGameStats,
  getTeamSeasonRoster,
} from "@/lib/chart-queries";
import {
  chartsAdjustedFixture,
  chartsAdjustedWeeksFixture,
  chartsGameRowsFixture,
  chartsRosterFixture,
  chartsSlateFixture,
} from "@/test/fixtures/charts";
import { ChartsView } from "@/components/charts/ChartsView";
import { WeekNav } from "@/components/WeekNav";

export const revalidate = 300;

const KINDS: ChartKind[] = ["net-success", "efficiency", "adjusted"];

type SearchParams = Promise<{ chart?: string; side?: string; week?: string; fixture?: string }>;

type Loaded =
  | { state: "unsupported" }
  | { state: "unavailable" }
  | {
      state: "ready";
      roster: RosterRow[];
      rows: TeamGameRow[];
      adjustedWeeks: number[];
      adjustedFor: (asOfWeek: number) => Promise<AdjustedRow[]>;
    };

async function load(season: number, fixture: string | undefined): Promise<Loaded> {
  if (process.env.CFB_UI_TEST_MODE === "1") {
    if (fixture === "unsupported") return { state: "unsupported" };
    if (fixture === "error") return { state: "unavailable" };
    if (fixture === "slate") {
      return { state: "ready", ...chartsSlateFixture(), adjustedWeeks: [], adjustedFor: async () => [] };
    }
    return {
      state: "ready",
      roster: chartsRosterFixture,
      rows: chartsGameRowsFixture,
      adjustedWeeks: chartsAdjustedWeeksFixture,
      adjustedFor: async (asOfWeek) => {
        if (fixture === "adjusted-error") throw new Error("adjusted window failed");
        return chartsAdjustedFixture(asOfWeek);
      },
    };
  }
  try {
    const [roster, rows, adjustedWeeks] = await Promise.all([
      getTeamSeasonRoster(season),
      getTeamGameStats(season),
      getTeamAdjustedWeeks(season),
    ]);
    // Null: no active release, or one staged before the chart projections existed.
    if (!roster || !rows || !adjustedWeeks) return { state: "unsupported" };
    return {
      state: "ready",
      roster,
      rows,
      adjustedWeeks,
      adjustedFor: async (asOfWeek) => (await getTeamAdjustedEpa(season, asOfWeek)) ?? [],
    };
  } catch (error) {
    console.error("Team charts query failed", error);
    return { state: "unavailable" };
  }
}

function notice(text: string) {
  return (
    <p role="status" className="rounded-xl border border-line bg-surface-card p-5 text-ink-muted" data-testid="charts-notice">
      {text}
    </p>
  );
}

export default async function ChartsPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const season = publicationScope.season;
  const kind: ChartKind = KINDS.includes(params.chart as ChartKind) ? (params.chart as ChartKind) : "net-success";
  const side: Side = params.side === "defense" ? "defense" : "offense";
  const requested = params.week !== undefined && /^\d{1,2}$/.test(params.week) ? Number(params.week) : null;

  const loaded = await load(season, params.fixture);

  let body: React.ReactNode;
  let tabs: React.ReactNode = null;
  let weekNav: React.ReactNode = null;
  if (loaded.state === "unsupported") {
    body = notice("Charts arrive with the next weekly release.");
  } else if (loaded.state === "unavailable") {
    body = notice("Charts are temporarily unavailable.");
  } else {
    const { roster, rows, adjustedWeeks } = loaded;
    const weeksOf: Record<ChartKind, number[]> = {
      "net-success": netSuccessWeeks(rows),
      efficiency: efficiencyThroughWeeks(rows),
      adjusted: adjustedThroughWeeks(adjustedWeeks),
    };
    const available = weeksOf[kind];
    const week = coerceWeek(requested, available);

    const query = (target: ChartKind, targetSide: Side, targetWeek: number | null) => {
      const q = new URLSearchParams({ chart: target });
      if (target === "efficiency") q.set("side", targetSide);
      if (targetWeek !== null) q.set("week", String(targetWeek));
      return `/charts?${q.toString()}`;
    };

    tabs = (
      <nav className="flex flex-wrap items-center gap-1.5" aria-label="Chart type">
        {KINDS.map((target) => {
          const active = target === kind;
          // The tab link carries the week coerced for that chart.
          const href = query(target, side, coerceWeek(week ?? requested, weeksOf[target]));
          return (
            <Link
              key={target}
              href={href}
              aria-current={active ? "page" : undefined}
              className={clsx(
                "rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-accent sm:text-sm",
                active ? "bg-accent text-white shadow-2xs" : "border border-line bg-surface-card text-ink-muted hover:bg-surface-inset",
              )}
            >
              {CHART_TAB_LABELS[target]}
            </Link>
          );
        })}
        {kind === "efficiency" && (
          <span className="ml-auto inline-flex gap-1" role="group" aria-label="Side of the ball">
            {(["offense", "defense"] as const).map((target) => (
              <Link
                key={target}
                href={query("efficiency", target, week)}
                aria-current={side === target ? "true" : undefined}
                className={clsx(
                  "rounded-lg px-2.5 py-1.5 text-xs font-semibold capitalize focus-visible:outline-2 focus-visible:outline-accent",
                  side === target ? "bg-ink text-surface-card" : "border border-line bg-surface-card text-ink-muted hover:bg-surface-inset",
                )}
              >
                {target}
              </Link>
            ))}
          </span>
        )}
      </nav>
    );

    if (week === null) {
      body = notice(
        kind === "net-success"
          ? "No completed games are published yet."
          : "This chart starts after Week 2 is complete.",
      );
    } else {
      weekNav = (
        <WeekNav
          season={season}
          week={week}
          weeks={available}
          basePath="/charts"
          labelMode={kind === "net-success" ? "week" : "through-week"}
        />
      );
      if (kind === "net-success") {
        const { bars, notCharted } = netSuccessBars(rows, week);
        body = <ChartsView kind={kind} side={side} season={season} week={week} roster={roster} bars={bars} notCharted={notCharted} />;
      } else if (kind === "efficiency") {
        body = <ChartsView kind={kind} side={side} season={season} week={week} roster={roster} scatter={efficiencyPoints(roster, rows, week, side)} />;
      } else {
        // "Through Week N" is the window with as_of_week N + 1.
        let adjustedRows: AdjustedRow[] | null = null;
        try {
          adjustedRows = await loaded.adjustedFor(week + 1);
        } catch (error) {
          console.error("Team charts adjusted query failed", error);
        }
        if (adjustedRows) {
          body = <ChartsView kind={kind} side={side} season={season} week={week} roster={roster} scatter={adjustedPoints(roster, adjustedRows)} />;
        } else {
          weekNav = null;
          body = notice("Charts are temporarily unavailable.");
        }
      }
    }
  }

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 space-y-4 px-4 py-3 sm:py-6">
      <div>
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-accent-ink">
          <span>{season}</span>
          <span className="text-ink-faint">·</span>
          <span>FBS vs FBS</span>
        </div>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink sm:text-3xl">Team charts</h1>
        <p className="mt-1 text-xs text-ink-muted sm:text-sm">
          Weekly team analysis reconstructed from the current release&apos;s data. It does not feed the ratings or picks.
        </p>
      </div>
      {tabs}
      {weekNav}
      {body}
    </main>
  );
}
