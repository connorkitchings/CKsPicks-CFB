import { displayOnlyNotice, isDisplayOnlyNoticeEnabled } from "@/lib/display-only";
import {
  getGamesForWeek,
  getMarketGamesForWeek,
  getRunForWeek,
  type Game,
} from "@/lib/queries";
import { getTeamSeasonRoster } from "@/lib/chart-queries";
import type { RosterRow } from "@/lib/conferences";
import { getV5PerformanceSplit, type Performance } from "@/lib/v5";
import { selectsV5, V5_INTENDED_UPDATE_MODEL_ID } from "@/lib/run-selection";
import { publicationScope, isAllowedSeason } from "@/lib/publication";
import { uiFixture } from "@/test/fixtures/publication";

export type SlateSearchParams = Promise<{
  season?: string;
  week?: string;
  mode?: string;
  sort?: string;
}>;
type ResolvedParams = Awaited<SlateSearchParams>;

export type SlateKind = "picks" | "results";
export type SlateSort = "kickoff" | "spreadEdge" | "totalEdge";

export const isUiTestMode = () => process.env.CFB_UI_TEST_MODE === "1";

/** The `?mode=` override is honored only under the UI test harness. */
export function slatePublicationMode(params: ResolvedParams): "predictions" | "market" {
  const override = params.mode === "predictions" || params.mode === "market" ? params.mode : null;
  return isUiTestMode() && override ? override : publicationScope.mode;
}

export function slateSort(params: ResolvedParams): SlateSort {
  return params.sort === "spreadEdge" || params.sort === "totalEdge" ? params.sort : "kickoff";
}

export function slateSeason(params: ResolvedParams): number {
  const requested = params.season ? Number(params.season) : publicationScope.season;
  return isAllowedSeason(requested) ? requested : publicationScope.season;
}

export type SlateData = {
  games: Game[];
  /** FBS teams and conferences for the conference filter; empty when the release has none. */
  roster: RosterRow[];
  performance: Performance[];
  systemName: string | null;
  retrospectiveRepair: boolean;
  displayOnlyText: string | null;
  dbError: string | null;
  /** Set only by the UI test fixtures, which pin the week they render. */
  fixtureWeek?: { week: number; weeks: number[] };
};

/**
 * Games and the model record for one slate. Picks gets the season record before the
 * week; Results gets that week's own record, so the two views never share a scope.
 */
export async function loadSlateData(args: {
  view: SlateKind;
  season: number;
  week: number;
  publicationMode: "predictions" | "market";
  /** Present when the caller already failed to resolve its target. */
  dbError?: string | null;
}): Promise<SlateData> {
  const { view, season, week, publicationMode } = args;
  const out: SlateData = {
    games: [],
    roster: [],
    performance: [],
    systemName: null,
    retrospectiveRepair: false,
    displayOnlyText: null,
    dbError: args.dbError ?? null,
  };

  if (isUiTestMode()) {
    if (publicationMode === "predictions") {
      const fx = await import("@/test/fixtures/slate");
      const bundle = view === "picks" ? fx.slatePicks() : fx.slateResults();
      out.games = bundle.games;
      out.roster = fx.slateRosterFixture;
      out.fixtureWeek = { week: bundle.week, weeks: bundle.weeks };
      if (bundle.games[0]?.publicationMode === "predictions") {
        out.systemName = bundle.games[0].systemName;
        out.performance = selectsV5(bundle.games[0].modelId) ? bundle.performance : [];
      }
    } else {
      out.games = uiFixture(publicationMode, week).games;
    }
    return out;
  }
  if (out.dbError || season <= 0 || week < 0) return out;

  try {
    if (publicationMode === "predictions") {
      const run = await getRunForWeek(season, week);
      out.retrospectiveRepair = run?.modelId === V5_INTENDED_UPDATE_MODEL_ID
        && run.evidenceClass === "replay";
      out.displayOnlyText = run?.displayOnly && isDisplayOnlyNoticeEnabled()
        ? displayOnlyNotice(week, run.createdAt)
        : null;
      const isV5 = selectsV5(run?.modelId) || (season === 2026 && run === null);
      let roster: RosterRow[] | null;
      [out.games, out.performance, roster] = await Promise.all([
        getGamesForWeek(season, week),
        isV5
          ? getV5PerformanceSplit(season, week).then((split) => (view === "picks" ? split.before : split.week))
          : Promise.resolve([]),
        // Optional: a missing roster only removes the conference filter, but say so.
        getTeamSeasonRoster(season).catch((err) => {
          console.error("Team roster query failed; the conference filter is hidden", err);
          return null;
        }),
      ]);
      out.roster = roster ?? [];
    } else {
      out.games = await getMarketGamesForWeek(season, week);
    }
    if (out.games[0]?.publicationMode === "predictions") out.systemName = out.games[0].systemName;
  } catch (err) {
    console.error(`${view} weekly data query failed`, err);
    out.dbError = view === "picks"
      ? "Weekly data is temporarily unavailable."
      : "Weekly results data is temporarily unavailable.";
  }
  return out;
}

/** Latest game update, falling back to the caller's timestamp. */
export function slateUpdatedAt(games: Game[], fallback: Date | null): Date | null {
  const latest = games.reduce<number>((max, g) => Math.max(max, g.updatedAt.getTime()), 0);
  return latest > 0 ? new Date(latest) : fallback;
}
