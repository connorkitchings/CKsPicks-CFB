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
  withYardage,
  type AdjustedRow,
  type ChartKind,
  type PossessionRow,
  type RatingSnapshotRow,
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
  parsePossessionMetric,
  parseRatingMetric,
  parseSide,
  pickerGroups,
} from "@/lib/chart-config";
import { publicationScope } from "@/lib/publication";
import {
  getTeamAdjustedEpa,
  getTeamAdjustedWeeks,
  getTeamGameStats,
  getTeamGameYardage,
  getTeamPossessionAdjusted,
  getTeamPossessionWeeks,
  getTeamSeasonRoster,
  getV5RatingSnapshots,
} from "@/lib/chart-queries";
import {
  chartsAdjustedFixture,
  chartsAdjustedWeeksFixture,
  chartsGameRowsFixture,
  chartsPossessionFixture,
  chartsPossessionWeeksFixture,
  chartsRatingSnapshotsFixture,
  chartsRosterFixture,
  chartsSlateFixture,
  chartsYardageFixture,
} from "@/test/fixtures/charts";
import { ChartLink } from "@/components/charts/ChartLink";
import { ChartsView, type ChartPayload } from "@/components/charts/ChartsView";
import { Header, Footer } from "@/components/Header";
import { PageHeading } from "@/components/ui/PageHeading";
import { segmentedGroupClass, segmentedItemClass } from "@/components/ui/SegmentedControl";
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
      /** Stored `team_possession_adjusted` windows (`as_of_week`). */
      possessionWeeks: number[];
      possessionFor: (asOfWeek: number) => Promise<PossessionRow[]>;
      /** `current` V5 rating snapshots of every stored week. */
      ratingSnapshots: () => Promise<RatingSnapshotRow[]>;
    };

/** Fixture releases without possession windows or rating snapshots. */
const NO_V5_ROWS = { possessionWeeks: [], possessionFor: async () => [], ratingSnapshots: async () => [] };

async function load(season: number, fixture: string | undefined): Promise<Loaded> {
  if (process.env.CFB_UI_TEST_MODE === "1") {
    if (fixture === "unsupported") return { state: "unsupported" };
    if (fixture === "error") return { state: "unavailable" };
    if (fixture === "slate") {
      const { roster, rows, yardage } = chartsSlateFixture();
      return { state: "ready", roster, rows: withYardage(rows, yardage), explosiveness: true, adjustedWeeks: [], adjustedFor: async () => [], ...NO_V5_ROWS };
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
      possessionWeeks: chartsPossessionWeeksFixture,
      possessionFor: async (asOfWeek) => {
        if (fixture === "adjusted-error") throw new Error("possession window failed");
        return chartsPossessionFixture(asOfWeek);
      },
      ratingSnapshots: async () => {
        if (fixture === "adjusted-error") throw new Error("rating snapshots failed");
        return chartsRatingSnapshotsFixture();
      },
    };
  }
  try {
    const [roster, rows, yardage, adjustedWeeks, possessionWeeks] = await Promise.all([
      getTeamSeasonRoster(season),
      getTeamGameStats(season),
      getTeamGameYardage(season),
      getTeamAdjustedWeeks(season),
      getTeamPossessionWeeks(season),
    ]);
    // Null: no active release, or one staged before the chart projections existed.
    if (!roster || !rows || !adjustedWeeks || !possessionWeeks) return { state: "unsupported" };
    // Yardage is null unless the release's chart set is `charts_v2`.
    return {
      state: "ready",
      roster,
      rows: yardage ? withYardage(rows, yardage) : rows,
      explosiveness: yardage !== null,
      adjustedWeeks,
      adjustedFor: async (asOfWeek) => (await getTeamAdjustedEpa(season, asOfWeek)) ?? [],
      possessionWeeks,
      possessionFor: async (asOfWeek) => (await getTeamPossessionAdjusted(season, asOfWeek)) ?? [],
      ratingSnapshots: async () => (await getV5RatingSnapshots(season)) ?? [],
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
  // Only `ready` kinds parse, so a hidden chart's branch below (and its lazy query) never runs.
  const kind = parseChartKind(params.chart);
  const side: Side = parseSide(params.side);
  const requested = params.week !== undefined && /^\d{1,2}$/.test(params.week) ? Number(params.week) : null;

  const loaded = await load(season, params.fixture);

  let body: React.ReactNode;
  let tabs: React.ReactNode = null;
  if (loaded.state === "unsupported") {
    body = notice("Charts arrive with the next weekly release.");
  } else if (loaded.state === "unavailable") {
    body = notice("Charts are temporarily unavailable.");
  } else {
    const { roster, rows, explosiveness, adjustedWeeks, possessionWeeks } = loaded;
    const weeksFor = (target: ChartKind): number[] => {
      switch (target) {
        case "net-success":
          return netSuccessWeeks(rows);
        case "efficiency":
          return efficiencyThroughWeeks(rows);
        case "adjusted":
          return adjustedThroughWeeks(adjustedWeeks);
        case "possession":
          return adjustedThroughWeeks(possessionWeeks);
        default:
          return [];
      }
    };
    const available = weeksFor(kind);
    const week = coerceWeek(requested, available);

    tabs = (
      // Phones scroll the tab row edge to edge; wider screens wrap whole groups.
      <nav className="-mx-4 flex items-end gap-x-5 gap-y-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:px-0 sm:pb-0" aria-label="Chart type" data-testid="chart-picker">
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

    // Side links and the week stepper join the chart's controls row through `settings`.
    const sideNav = CHART_REGISTRY[kind].controls.side && (
      <div className={segmentedGroupClass("sm")} role="group" aria-label="Side of the ball">
        {(["offense", "defense"] as const).map((target) => (
          <ChartLink
            key={target}
            href={chartHref(kind, { side: target, week })}
            aria-current={side === target ? "true" : undefined}
            className={clsx(segmentedItemClass(side === target, "sm"), "capitalize")}
          >
            {target}
          </ChartLink>
        ))}
      </div>
    );
    const view = (viewWeek: number, chart: ChartPayload, weekNav: React.ReactNode = null) => (
      <ChartsView season={season} week={viewWeek} roster={roster} chart={chart} settings={<>{sideNav}{weekNav}</>} />
    );

    if (kind === "rating-trajectory") {
      // Every stored snapshot week (Through Week 0 on) at once, so there is no week selector.
      let snapshots: RatingSnapshotRow[] | null = null;
      try {
        snapshots = await loaded.ratingSnapshots();
      } catch (error) {
        console.error("Team charts rating snapshot query failed", error);
      }
      body = !snapshots
        ? notice("Charts are temporarily unavailable.")
        : !snapshots.length
          ? notice("No V5 rating snapshots are published yet.")
          : view(Math.max(...snapshots.map((row) => row.week)), { kind, rows: snapshots, initialMetric: parseRatingMetric(params.metric) });
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
        : view(charted[charted.length - 1], { kind, rows, adjusted, initialMetric: parseGameLogMetric(params.metric, explosiveness), explosiveness });
    } else if (week === null) {
      body = notice(
        kind === "net-success"
          ? "No completed games are published yet."
          : "This chart starts after Week 2 is complete.",
      );
    } else {
      const weekNav = (
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
        body = view(week, { kind, bars, notCharted }, weekNav);
      } else if (kind === "efficiency") {
        // Without yardage the chart is success rate vs PPA/play, with no metric toggle.
        const initialMetric = parseEfficiencyMetric(params.metric, explosiveness);
        body = view(week, { kind, side, rows, initialMetric, explosiveness }, weekNav);
      } else if (kind === "possession") {
        // "Through Week N" is the window with as_of_week N + 1.
        let possessionRows: PossessionRow[] | null = null;
        try {
          possessionRows = await loaded.possessionFor(week + 1);
        } catch (error) {
          console.error("Team charts possession query failed", error);
        }
        body = possessionRows
          ? view(week, { kind, rows: possessionRows, initialMetric: parsePossessionMetric(params.metric) }, weekNav)
          : notice("Charts are temporarily unavailable.");
      } else if (kind === "adjusted") {
        // "Through Week N" is the window with as_of_week N + 1.
        let adjustedRows: AdjustedRow[] | null = null;
        try {
          adjustedRows = await loaded.adjustedFor(week + 1);
        } catch (error) {
          console.error("Team charts adjusted query failed", error);
        }
        if (adjustedRows) {
          body = view(week, { kind, scatter: adjustedPoints(roster, adjustedRows) }, weekNav);
        } else {
          body = notice("Charts are temporarily unavailable.");
        }
      } else {
        // Registered kinds that are not `ready` never parse from the URL.
        body = notice("This chart is not available yet.");
      }
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header
        season={season}
        systemName={null}
        updatedAt={null}
        publicationMode={publicationScope.mode}
        allowedSeasons={publicationScope.allowedSeasons}
        containerWidth="max-w-6xl"
      />
      <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 space-y-3 px-4 py-3 sm:py-4">
        <PageHeading title="Team charts">
          {season}
          <span className="text-ink-faint"> · </span>
          {CHART_REGISTRY[kind].population}
        </PageHeading>
        {tabs}
        {body}
      </main>
      <Footer publicationMode={publicationScope.mode} containerWidth="max-w-6xl" />
    </div>
  );
}
