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
import type { SlateSort } from "@/lib/slate";
import { selectsV5, V5_INTENDED_UPDATE_MODEL_ID } from "@/lib/run-selection";
import { publicationScope, resolveSeasonParam } from "@/lib/publication";
import { uiFixture } from "@/test/fixtures/publication";

export type SlateSearchParams = Promise<{
  season?: string;
  week?: string;
  mode?: string;
  sort?: string;
  now?: string;
}>;
type ResolvedParams = Awaited<SlateSearchParams>;


export const isUiTestMode = () => process.env.CFB_UI_TEST_MODE === "1";

/** The UI-test clock: before every fixture kickoff, so fixture games read exactly as scored or upcoming. */
export const UI_TEST_NOW = new Date("2026-08-01T12:00:00Z");

/**
 * The page clock. Under the UI test harness it is `UI_TEST_NOW`, or the `?now=` ISO timestamp when valid;
 * anywhere else it is the real time and `?now=` is ignored.
 */
export function pageNow(params?: ResolvedParams): Date {
  if (!isUiTestMode()) return new Date();
  const override = params?.now ? new Date(params.now) : null;
  return override && !Number.isNaN(override.getTime()) ? override : UI_TEST_NOW;
}

/** The `?mode=` override is honored only under the UI test harness. */
export function slatePublicationMode(params: ResolvedParams): "predictions" | "market" {
  const override = params.mode === "predictions" || params.mode === "market" ? params.mode : null;
  return isUiTestMode() && override ? override : publicationScope.mode;
}

export function slateSort(params: ResolvedParams): SlateSort {
  const sorts: readonly string[] = ["bestEdge", "spreadEdge", "totalEdge", "bestResult", "worstResult"];
  return sorts.includes(params.sort ?? "") ? (params.sort as SlateSort) : "kickoff";
}

export function slateSeason(params: ResolvedParams): number {
  return resolveSeasonParam(params.season, publicationScope.season);
}

export type SlateData = {
  games: Game[];
  /** FBS teams and conferences for the conference filter; empty when the release has none. */
  roster: RosterRow[];
  /** Season record before the week. */
  performance: Performance[];
  /** The week's own record and accuracy; empty until a game is graded. */
  weekPerformance: Performance[];
  systemName: string | null;
  retrospectiveRepair: boolean;
  displayOnlyText: string | null;
  dbError: string | null;
  /** Set only by the UI test fixtures, which pin the week they render. */
  fixtureWeek?: { week: number; weeks: number[] };
};

/** Games plus the model record before the week and the week's own record. */
export async function loadSlateData(args: {
  season: number;
  week: number;
  publicationMode: "predictions" | "market";
  /** Present when the caller already failed to resolve its target. */
  dbError?: string | null;
}): Promise<SlateData> {
  const { season, week, publicationMode } = args;
  const out: SlateData = {
    games: [],
    roster: [],
    performance: [],
    weekPerformance: [],
    systemName: null,
    retrospectiveRepair: false,
    displayOnlyText: null,
    dbError: args.dbError ?? null,
  };

  if (isUiTestMode()) {
    if (publicationMode === "predictions") {
      const fx = await import("@/test/fixtures/slate");
      const bundle = week === 4 ? fx.slateResults() : week === 6 ? fx.slatePartial() : fx.slatePicks();
      out.games = bundle.games;
      out.roster = fx.slateRosterFixture;
      out.fixtureWeek = { week: bundle.week, weeks: bundle.weeks };
      if (bundle.games[0]?.publicationMode === "predictions") {
        out.systemName = bundle.games[0].systemName;
        const v5 = selectsV5(bundle.games[0].modelId);
        out.performance = v5 ? bundle.performance : [];
        out.weekPerformance = v5 ? bundle.performance : [];
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
      let split: { before: Performance[]; week: Performance[] } | null;
      [out.games, split, roster] = await Promise.all([
        getGamesForWeek(season, week),
        isV5 ? getV5PerformanceSplit(season, week) : Promise.resolve(null),
        // Optional: a missing roster only removes the conference filter, but say so.
        getTeamSeasonRoster(season).catch((err) => {
          console.error("Team roster query failed; the conference filter is hidden", err);
          return null;
        }),
      ]);
      out.performance = split?.before ?? [];
      out.weekPerformance = split?.week ?? [];
      out.roster = roster ?? [];
    } else {
      out.games = await getMarketGamesForWeek(season, week);
    }
    if (out.games[0]?.publicationMode === "predictions") out.systemName = out.games[0].systemName;
  } catch (err) {
    console.error("Weekly data query failed", err);
    out.dbError = "Weekly data is temporarily unavailable.";
  }
  return out;
}

/** Latest game update, falling back to the caller's timestamp. */
export function slateUpdatedAt(games: Game[], fallback: Date | null): Date | null {
  const latest = games.reduce<number>((max, g) => Math.max(max, g.updatedAt.getTime()), 0);
  return latest > 0 ? new Date(latest) : fallback;
}
