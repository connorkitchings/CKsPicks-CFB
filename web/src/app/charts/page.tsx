import clsx from "clsx";
import { notFound } from "next/navigation";
import { isChartsEnabled } from "@/lib/charts-gate";
import {
  adjustedPoints,
  adjustedThroughWeeks,
  coerceWeek,
  efficiencyThroughWeeks,
  netSuccessBars,
  netSuccessWeeks,
  scheduleRows,
  withYardage,
  type AdjustedRow,
  type ChartKind,
  type RosterRow,
  type Side,
  type TeamGameRow,
} from "@/lib/charts";
import {
  CHART_REGISTRY,
  chartHref,
  parseChartKind,
  parseEfficiencyMetric,
  parseGameLogMetric,
  parseSide,
  parseTrajectoryMetric,
  pickerGroups,
} from "@/lib/chart-config";
import { publicationScope } from "@/lib/publication";
import {
  getTeamAdjustedEpa,
  getTeamAdjustedEpaAll,
  getTeamAdjustedWeeks,
  getTeamGameStats,
  getTeamGameYardage,
  getTeamSeasonRoster,
} from "@/lib/chart-queries";
import {
  chartsAdjustedFixture,
  chartsAdjustedWeeksFixture,
  chartsGameRowsFixture,
  chartsRosterFixture,
  chartsScheduleFixture,
  chartsSlateFixture,
  chartsYardageFixture,
} from "@/test/fixtures/charts";
import { ChartLink } from "@/components/charts/ChartLink";
import { ChartsView } from "@/components/charts/ChartsView";
import { WeekNav } from "@/components/WeekNav";

export const revalidate = 300;

type SearchParams = Promise<{ chart?: string; side?: string; week?: string; fixture?: string; metric?: string; team?: string }>;

type Loaded =
  | { state: "unsupported" }
  | { state: "unavailable" }
  | {
      state: "ready";
      roster: RosterRow[];
      rows: TeamGameRow[];
      /** The release serves `team_game_yardage` (`charts_v2`), joined onto `rows`. */
      explosiveness: boolean;
      adjustedWeeks: number[];
      adjustedFor: (asOfWeek: number) => Promise<AdjustedRow[]>;
      /** Every stored window (the trajectory chart). */
      adjustedAll: () => Promise<AdjustedRow[]>;
    };

async function load(season: number, fixture: string | undefined): Promise<Loaded> {
  if (process.env.CFB_UI_TEST_MODE === "1") {
    if (fixture === "unsupported") return { state: "unsupported" };
    if (fixture === "error") return { state: "unavailable" };
    if (fixture === "schedule") {
      const { roster, rows, yardage, adjustedWeeks, adjustedFor } = chartsScheduleFixture();
      return {
        state: "ready", roster, rows: withYardage(rows, yardage), explosiveness: true,
        adjustedWeeks, adjustedFor: async (asOfWeek) => adjustedFor(asOfWeek),
        adjustedAll: async () => adjustedWeeks.flatMap(adjustedFor),
      };
    }
    if (fixture === "slate") {
      const { roster, rows, yardage } = chartsSlateFixture();
      return { state: "ready", roster, rows: withYardage(rows, yardage), explosiveness: true, adjustedWeeks: [], adjustedFor: async () => [], adjustedAll: async () => [] };
    }
    // `v1`: a retained `charts_v1` release (no yardage); otherwise `charts_v2`.
    const explosiveness = fixture !== "v1";
    return {
      state: "ready",
      roster: chartsRosterFixture,
      rows: explosiveness ? withYardage(chartsGameRowsFixture, chartsYardageFixture) : chartsGameRowsFixture,
      explosiveness,
      adjustedWeeks: chartsAdjustedWeeksFixture,
      adjustedFor: async (asOfWeek) => {
        if (fixture === "adjusted-error") throw new Error("adjusted window failed");
        return chartsAdjustedFixture(asOfWeek);
      },
      adjustedAll: async () => {
        if (fixture === "adjusted-error") throw new Error("adjusted windows failed");
        return chartsAdjustedWeeksFixture.flatMap((asOfWeek) => chartsAdjustedFixture(asOfWeek));
      },
    };
  }
  try {
    const [roster, rows, yardage, adjustedWeeks] = await Promise.all([
      getTeamSeasonRoster(season),
      getTeamGameStats(season),
      getTeamGameYardage(season),
      getTeamAdjustedWeeks(season),
    ]);
    // Null: no active release, or one staged before the chart projections existed.
    if (!roster || !rows || !adjustedWeeks) return { state: "unsupported" };
    // Yardage is null unless the release's chart set is `charts_v2`.
    return {
      state: "ready",
      roster,
      rows: yardage ? withYardage(rows, yardage) : rows,
      explosiveness: yardage !== null,
      adjustedWeeks,
      adjustedFor: async (asOfWeek) => (await getTeamAdjustedEpa(season, asOfWeek)) ?? [],
      adjustedAll: async () => (await getTeamAdjustedEpaAll(season)) ?? [],
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

/** Keep the disabled response synchronous, ahead of the ancestor loading boundary. */
export default function ChartsPage(props: { searchParams: SearchParams }) {
  if (!isChartsEnabled()) notFound();
  return <EnabledChartsPage {...props} />;
}

async function EnabledChartsPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const season = publicationScope.season;
  const kind = parseChartKind(params.chart);
  const side: Side = parseSide(params.side);
  const requested = params.week !== undefined && /^\d{1,2}$/.test(params.week) ? Number(params.week) : null;

  const loaded = await load(season, params.fixture);

  let body: React.ReactNode;
  let tabs: React.ReactNode = null;
  let weekNav: React.ReactNode = null;
  let sideNav: React.ReactNode = null;
  if (loaded.state === "unsupported") {
    body = notice("Charts arrive with the next weekly release.");
  } else if (loaded.state === "unavailable") {
    body = notice("Charts are temporarily unavailable.");
  } else {
    const { roster, rows, explosiveness, adjustedWeeks } = loaded;
    const weeksFor = (target: ChartKind): number[] => {
      switch (target) {
        case "net-success":
          return netSuccessWeeks(rows);
        case "efficiency":
          return efficiencyThroughWeeks(rows);
        case "adjusted":
        case "schedule":
          return adjustedThroughWeeks(adjustedWeeks);
        default:
          return [];
      }
    };
    const available = weeksFor(kind);
    const week = coerceWeek(requested, available);

    tabs = (
      <nav className="-mx-1 flex w-full min-w-0 max-w-full sm:w-auto items-end gap-3 overflow-x-auto px-1 pb-1 sm:flex-wrap sm:overflow-visible sm:pb-0" aria-label="Chart type" data-testid="chart-picker">
        {pickerGroups().map((group) => (
          <div key={group.id} className="flex shrink-0 flex-col gap-1" role="group" aria-label={group.label}>
            <span className="px-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-faint" aria-hidden>
              {group.label}
            </span>
            <div className="flex gap-1.5">
              {group.kinds.map((target) => {
                const active = target === kind;
                // The link carries the week coerced for that chart; ChartLink adds `team`.
                const href = chartHref(target, { side, week: coerceWeek(week ?? requested, weeksFor(target)) });
                return (
                  <ChartLink
                    key={target}
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={clsx(
                      "inline-flex min-h-10 items-center whitespace-nowrap rounded-lg px-3 py-2 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent sm:text-sm",
                      active ? "bg-accent text-white shadow-2xs" : "border border-line bg-surface-card text-ink-muted hover:bg-surface-inset",
                    )}
                  >
                    {CHART_REGISTRY[target].tabLabel}
                  </ChartLink>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    );

    if (CHART_REGISTRY[kind].controls.side) {
      sideNav = (
        <div className="flex items-center gap-2" role="group" aria-label="Side of the ball">
          <span className="text-xs font-semibold text-ink-muted">Side</span>
          <div className="inline-flex gap-1 rounded-lg border border-line bg-surface-card p-1">
            {(["offense", "defense"] as const).map((target) => (
              <ChartLink
                key={target}
                href={chartHref(kind, { side: target, week })}
                aria-current={side === target ? "true" : undefined}
                className={clsx(
                  "inline-flex min-h-8 items-center rounded-md px-2.5 py-1 text-xs font-semibold capitalize transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                  side === target ? "bg-ink text-surface-card shadow-2xs" : "text-ink-muted hover:bg-surface-inset hover:text-ink",
                )}
              >
                {target}
              </ChartLink>
            ))}
          </div>
        </div>
      );
    }

    if (kind === "trajectory") {
      // Every stored window at once, so there is no week selector.
      const throughWeeks = adjustedThroughWeeks(adjustedWeeks);
      let trajectoryRows: AdjustedRow[] | null = null;
      if (throughWeeks.length) {
        try {
          trajectoryRows = await loaded.adjustedAll();
        } catch (error) {
          console.error("Team charts trajectory query failed", error);
        }
      }
      body = !throughWeeks.length
        ? notice("This chart starts after Week 2 is complete.")
        : trajectoryRows
          ? <ChartsView season={season} week={throughWeeks[throughWeeks.length - 1]} roster={roster} chart={{ kind, rows: trajectoryRows, initialMetric: parseTrajectoryMetric(params.metric) }} />
          : notice("Charts are temporarily unavailable.");
    } else if (kind === "game-log") {
      // The whole release with no week selector; the latest adjusted window picks the default team.
      const charted = netSuccessWeeks(rows);
      const latestWindow = adjustedWeeks.length ? Math.max(...adjustedWeeks) : null;
      let adjusted: AdjustedRow[] = [];
      if (latestWindow !== null) {
        try {
          adjusted = await loaded.adjustedFor(latestWindow);
        } catch (error) {
          console.error("Team charts game-log adjusted query failed", error);
        }
      }
      body = !charted.length
        ? notice("No completed games are published yet.")
        : <ChartsView season={season} week={charted[charted.length - 1]} roster={roster} chart={{ kind, rows, adjusted, initialMetric: parseGameLogMetric(params.metric, explosiveness), explosiveness }} />;
    } else if (week === null) {
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
          compact
          labelMode={CHART_REGISTRY[kind].controls.week === "week" ? "week" : "through-week"}
        />
      );
      if (kind === "net-success") {
        const { bars, notCharted } = netSuccessBars(rows, week);
        body = <ChartsView season={season} week={week} roster={roster} chart={{ kind, bars, notCharted }} />;
      } else if (kind === "efficiency") {
        // Without yardage the chart is success rate vs PPA/play, with no metric toggle.
        const initialMetric = parseEfficiencyMetric(params.metric, explosiveness);
        body = <ChartsView season={season} week={week} roster={roster} chart={{ kind, side, rows, initialMetric, explosiveness }} />;
      } else if (kind === "adjusted" || kind === "schedule") {
        // "Through Week N" is the window with as_of_week N + 1.
        let adjustedRows: AdjustedRow[] | null = null;
        try {
          adjustedRows = await loaded.adjustedFor(week + 1);
        } catch (error) {
          console.error("Team charts adjusted query failed", error);
        }
        if (adjustedRows) {
          const chart = kind === "adjusted"
            ? { kind, scatter: adjustedPoints(roster, adjustedRows) }
            : { kind, schedule: scheduleRows(roster, adjustedRows, side) };
          body = <ChartsView season={season} week={week} roster={roster} chart={chart} />;
        } else {
          weekNav = null;
          body = notice("Charts are temporarily unavailable.");
        }
      } else {
        // Registered kinds that are not `ready` never parse from the URL.
        body = notice("This chart is not available yet.");
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
          Compare weekly game performance and season-long team efficiency.
        </p>
      </div>
      {tabs && (
        <div className="flex flex-col gap-3 rounded-xl border border-line bg-surface-inset p-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
            {tabs}
            {sideNav}
          </div>
          {weekNav && <div className="flex items-center">{weekNav}</div>}
        </div>
      )}
      {body}
    </main>
  );
}
