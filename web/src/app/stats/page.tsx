import clsx from "clsx";
import { MobileStickyBar } from "@/components/ui/MobileStickyBar";
import { Notice } from "@/components/ui/Notice";
import {
  adjustedPoints,
  adjustedThroughWeeks,
  coerceWeek,
  efficiencyPoints,
  efficiencyThroughWeeks,
  netSuccessBars,
  netSuccessWeeks,
  withYardage,
  type AdjustedRow,
  type ChartKind,
  type EfficiencyMetric,
  type PossessionRow,
  type RatingSnapshotRow,
  type RosterRow,
  type Side,
  type SlateMarketGameRow,
  type TeamGameRow,
  type TeamResumeChartRow,
  type TeamSeasonStatRow,
} from "@/lib/charts";
import {
  CHART_REGISTRY,
  chartHref,
  parseChartKind,
  parseEfficiencyMetric,
  parseGameLogMetric,
  parseMarketBoardMetric,
  parsePossessionMetric,
  parseRatingMetric,
  parseSide,
  pickerGroups,
  SETTINGS_SLOT_ID,
} from "@/lib/chart-config";
import { publicationScope } from "@/lib/publication";
import { PHONE_PAGE_RHYTHM } from "@/lib/page-width";
import {
  getSlateMarketComparison,
  getSlateMarketWeeks,
  getTeamAdjustedEpa,
  getTeamAdjustedWeeks,
  getTeamGameStats,
  getTeamGameYardage,
  getTeamPossessionAdjusted,
  getTeamPossessionWeeks,
  getTeamResume,
  getTeamSeasonRoster,
  getTeamSeasonStatsSnapshot,
  getTeamSeasonStatsWeeks,
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
  chartsSeasonStatsFixture,
  chartsSeasonStatsWeeksFixture,
  chartsSlateFixture,
  chartsSlateMarketGamesFixture,
  chartsSlateMarketWeeksFixture,
  chartsTeamResumeFixture,
  chartsYardageFixture,
} from "@/test/fixtures/charts";
import { ChartLink } from "@/components/charts/ChartLink";
import { ChartSelect } from "@/components/charts/ChartSelect";
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
      seasonStatsWeeks: number[];
      seasonStatsFor: (asOfWeek: number) => Promise<TeamSeasonStatRow[]>;
      teamResume: () => Promise<TeamResumeChartRow[]>;
      slateWeeks: number[];
      slateGamesFor: (week: number) => Promise<SlateMarketGameRow[]>;
    };

/** Fixture releases without possession windows or rating snapshots. */
const NO_V5_ROWS = {
  possessionWeeks: [],
  possessionFor: async () => [],
  ratingSnapshots: async () => [],
  seasonStatsWeeks: [],
  seasonStatsFor: async () => [],
  teamResume: async () => [],
  slateWeeks: [],
  slateGamesFor: async () => [],
};

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
      seasonStatsWeeks: chartsSeasonStatsWeeksFixture,
      seasonStatsFor: async (asOfWeek) => {
        if (fixture === "adjusted-error") throw new Error("season stats window failed");
        return chartsSeasonStatsFixture(asOfWeek);
      },
      teamResume: async () => {
        if (fixture === "adjusted-error") throw new Error("team resume failed");
        return chartsTeamResumeFixture();
      },
      slateWeeks: chartsSlateMarketWeeksFixture,
      slateGamesFor: async (week) => {
        if (fixture === "adjusted-error") throw new Error("slate games failed");
        return chartsSlateMarketGamesFixture(week);
      },
    };
  }
  try {
    const [roster, rows, yardage, adjustedWeeks, possessionWeeks, seasonStatsWeeks, slateWeeks] = await Promise.all([
      getTeamSeasonRoster(season),
      getTeamGameStats(season),
      getTeamGameYardage(season),
      getTeamAdjustedWeeks(season),
      getTeamPossessionWeeks(season),
      getTeamSeasonStatsWeeks(season),
      getSlateMarketWeeks(season),
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
      seasonStatsWeeks: seasonStatsWeeks ?? [],
      seasonStatsFor: async (asOfWeek) => (await getTeamSeasonStatsSnapshot(season, asOfWeek)) ?? [],
      teamResume: async () => (await getTeamResume(season)) ?? [],
      slateWeeks: slateWeeks ?? [],
      slateGamesFor: async (week) => (await getSlateMarketComparison(season, week)) ?? [],
    };
  } catch (error) {
    console.error("Team charts query failed", error);
    return { state: "unavailable" };
  }
}

function notice(text: string) {
  return (
    <div data-testid="charts-notice">
      <Notice tone="empty">{text}</Notice>
    </div>
  );
}

export default async function ChartsPage({ searchParams }: { searchParams: SearchParams }) {
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
    const { roster, rows, explosiveness, adjustedWeeks, possessionWeeks, seasonStatsWeeks, slateWeeks } = loaded;
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
        case "downs":
        case "finishing-drives":
          return adjustedThroughWeeks(seasonStatsWeeks);
        case "resume-quality":
          return adjustedThroughWeeks(seasonStatsWeeks.length ? seasonStatsWeeks : adjustedWeeks);
        case "market-board":
          return slateWeeks;
        default:
          return [];
      }
    };
    const available = weeksFor(kind);
    const week = coerceWeek(requested, available);

    // On phones the nav itself is the sticky bar: a sticky child could not leave its short parent.
    tabs = (
      <MobileStickyBar as="nav" aria-label="Chart type" data-testid="chart-picker">
        <div className="hidden flex-wrap items-end gap-x-5 gap-y-2 sm:flex">
          {pickerGroups().map((group) => (
            <div key={group.id} className="flex shrink-0 flex-col gap-1" role="group" aria-label={group.label}>
              <span className="px-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-faint" aria-hidden>{group.label}</span>
              <div className="flex gap-1.5">
                {group.kinds.map((target) => (
                  <ChartLink
                    key={target}
                    href={chartHref(target, { side, week: coerceWeek(week ?? requested, weeksFor(target)) })}
                    aria-current={target === kind ? "page" : undefined}
                    className={clsx(
                      "inline-flex min-h-10 items-center whitespace-nowrap rounded-lg px-3 py-2 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                      target === kind ? "bg-accent text-white shadow-2xs" : "border border-line bg-surface-card text-ink-muted hover:bg-surface-inset",
                    )}
                  >{CHART_REGISTRY[target].tabLabel}</ChartLink>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-2 sm:hidden">
          <ChartSelect
            currentHref={chartHref(kind, { side, week: coerceWeek(week ?? requested, weeksFor(kind)) })}
            groups={pickerGroups().map((group) => ({
              id: group.id,
              label: group.label,
              options: group.kinds.map((target) => ({
                href: chartHref(target, { side, week: coerceWeek(week ?? requested, weeksFor(target)) }),
                label: CHART_REGISTRY[target].tabLabel,
              })),
            }))}
          />
          {/* Receives the phone settings trigger from MobileChartSettings (one settings tree, below in the chart frame). */}
          <div id={SETTINGS_SLOT_ID} className="min-w-11 shrink-0" />
        </div>
      </MobileStickyBar>
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
          basePath="/stats"
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
        const metrics: EfficiencyMetric[] = explosiveness ? ["ppa", "explosive_rate", "yards_per_success"] : ["ppa"];
        const data = Object.fromEntries(metrics.map((metric) => [metric, efficiencyPoints(roster, rows, week, side, metric)]));
        body = view(week, { kind, side, data, initialMetric, explosiveness }, weekNav);
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
      } else if (kind === "downs") {
        let statRows: TeamSeasonStatRow[] | null = null;
        try {
          statRows = await loaded.seasonStatsFor(week + 1);
        } catch (error) {
          console.error("Team charts downs query failed", error);
        }
        body = statRows
          ? view(week, { kind, rows: statRows, side }, weekNav)
          : notice("Charts are temporarily unavailable.");
      } else if (kind === "finishing-drives") {
        let statRows: TeamSeasonStatRow[] | null = null;
        try {
          statRows = await loaded.seasonStatsFor(week + 1);
        } catch (error) {
          console.error("Team charts finishing-drives query failed", error);
        }
        body = statRows
          ? view(week, { kind, rows: statRows, side }, weekNav)
          : notice("Charts are temporarily unavailable.");
      } else if (kind === "resume-quality") {
        let ratingRows: RatingSnapshotRow[] | null = null;
        let resumeRows: TeamResumeChartRow[] | null = null;
        try {
          [ratingRows, resumeRows] = await Promise.all([
            loaded.ratingSnapshots(),
            loaded.teamResume(),
          ]);
        } catch (error) {
          console.error("Team charts resume-quality query failed", error);
        }
        body = ratingRows && resumeRows
          ? view(week, { kind, ratings: ratingRows.filter((r) => r.week === week), resumeRows }, weekNav)
          : notice("Charts are temporarily unavailable.");
      } else if (kind === "market-board") {
        let slateGames: SlateMarketGameRow[] | null = null;
        try {
          slateGames = await loaded.slateGamesFor(week);
        } catch (error) {
          console.error("Team charts market-board query failed", error);
        }
        body = slateGames
          ? view(week, { kind, games: slateGames, initialMetric: parseMarketBoardMetric(params.metric) }, weekNav)
          : notice("Charts are temporarily unavailable.");
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
        width="slate"
      />
      <main id="main-content" tabIndex={-1} className={`mx-auto w-full max-w-6xl flex-1 px-4 sm:py-4 ${PHONE_PAGE_RHYTHM}`}>
        {/* Phones drop the visible heading (the sticky bar names the chart) but keep it for assistive tech. */}
        <div className="max-sm:sr-only">
          <PageHeading title="Team graphs">
            {season}
            <span className="text-ink-faint"> · </span>
            {CHART_REGISTRY[kind].population}
          </PageHeading>
        </div>
        {tabs}
        {body}
      </main>
      <Footer publicationMode={publicationScope.mode} width="slate" />
    </div>
  );
}
