import { isDisplayOnly } from "./display-only";
import { eq, asc, and, inArray, lte, sql, notLike, or } from "drizzle-orm";
import { cache } from "react";
import { db as legacyDb, schema } from "./db";
import { publicationScope } from "./publication.ts";
import { getSeasonDb, getSeasonReleaseContext } from "./season-release";
import { existsFrom } from "./db-result";
import { releaseCached, RUN_STATE_CACHE } from "./release-cache.ts";
import { tiedExistsSql } from "./tie-sql";
import { isSelectableRun, V5_RECORD_EVIDENCE } from "./run-selection";
import { selectGradedWeeks } from "./results-weeks.ts";

import { deriveSpreadView, deriveTotalView } from "./publication";
import { overlaySelection } from "./selection-overlay";
import {
  PREDICTION_GAME_SPEC,
  RowContractError,
  TEAM_STAT_RULES,
  TEAM_STAT_SPEC,
  guardRows,
} from "./row-guard.ts";
import type { TeamStatRow } from "./team-stats";
import { cachedOrTolerant, SwallowedReadError } from "./cached-or-tolerant.ts";
import { biggestEdgesRecord, leanFor, type LeanGradeRow, type Tally } from "./slate.ts";

type BaseGame = {
  gameId: number;
  season: number;
  week: number;
  startDate: Date;
  homeTeam: string;
  awayTeam: string;
  homeTeamSpreadLine: number | null;
  totalLine: number | null;
  updatedAt: Date;
  homePoints: number | null;
  awayPoints: number | null;
  /** Season W-L as of this game's kickoff (null before the first game). */
  homeRecord: string | null;
  awayRecord: string | null;
  /** Game venue location, when known (absent until game_venues is populated). */
  venueCity?: string | null;
  venueState?: string | null;
  neutralSite?: boolean | null;
};

/** Public-safe schedule and market projection with no model-only fields. */
export type MarketGame = BaseGame & {
  publicationMode: "market";
  /** Settled outcomes are public-safe; predictions and model metadata are not. */
  spreadResult: "win" | "loss" | "push" | null;
  totalResult: "win" | "loss" | "push" | null;
};

/** Prediction-bearing projection, selected only after explicit publication opt-in. */
export type PredictionGame = BaseGame & {
  publicationMode: "predictions";
  runId: string | null;
  runState: "preview" | "published" | "frozen" | "scored" | "legacy";
  predictedSpread: number | null;
  predictedTotal: number | null;
  predictedSpreadStdDev: number | null;
  predictedTotalStdDev: number | null;
  spreadLean: "home" | "away" | null;
  totalLean: "over" | "under" | null;
  edgeSpread: number | null;
  edgeTotal: number | null;
  highConfidence: boolean;
  systemName: string | null;
  modelId: string | null;
  evidenceClass?: "legacy" | "pending" | "replay" | "live" | "missed";
  regime: "preseason" | "one_game" | "two_games" | "three_games" | "game_1" | "game_2" | "game_3" | "game_4" | "established" | null;
  homeCompletedGames: number;
  awayCompletedGames: number;
  spreadModelVersion: string | null;
  totalModelVersion: string | null;
  spreadResult: "win" | "loss" | "push" | null;
  totalResult: "win" | "loss" | "push" | null;
  /**
   * Sportsbook behind the selected best quote for each target, when the run
   * recorded one. Null/absent when the line is a consensus fallback.
   */
  spreadSource?: string | null;
  totalSource?: string | null;
};

export type Game = MarketGame | PredictionGame;

/** YTD system record shape. */
export type Stats = {
  season: number;
  /** Last week with immutable grades in this selected-week snapshot. */
  asOfWeek: number | null;
  spreadWins: number;
  spreadLosses: number;
  spreadPushes: number;
  totalWins: number;
  totalLosses: number;
  totalPushes: number;
};

/** Diagnostic-only reconstructed historical comparison; never a live bet record. */
export type HistoricalContextPeriod = {
  comparisonSeason: number;
  comparisonWeek: number | null;
  spreadWins: number;
  spreadLosses: number;
  spreadPushes: number;
  spreadComparedGames: number;
  totalWins: number;
  totalLosses: number;
  totalPushes: number;
  totalComparedGames: number;
};

export type HistoricalModelContext = {
  modelId: string;
  fullSeason: HistoricalContextPeriod;
  matchingWeek: HistoricalContextPeriod | null;
};

/** Return the active { season, week, updatedAt } from the singleton current_week row. */
type CurrentWeek = { season: number; week: number; updatedAt: Date; activeRunId: string | null };

/** The release's active week; immutable per release (`site_week_selections` is release-scoped). */
const getReleaseCurrentWeek = releaseCached("getCurrentWeek", async (season: number): Promise<CurrentWeek> => {
  const release = await getSeasonReleaseContext(season);
  if (!release) throw new Error("No active season release");
  const db = await getSeasonDb(release.season);
  const rows = await db.select({ runId: schema.siteWeekSelections.runId })
    .from(schema.siteWeekSelections).where(and(
      eq(schema.siteWeekSelections.season, release.season),
      eq(schema.siteWeekSelections.week, release.activeWeek),
    )).limit(1);
  if (!rows[0]) throw new Error("Active season release lacks current week selection");
  return { season: release.season, week: release.activeWeek, updatedAt: release.activatedAt, activeRunId: rows[0].runId };
});

export const getCurrentWeek = cache(async (): Promise<CurrentWeek | null> => {
  const release = await getSeasonReleaseContext();
  if (release) return getReleaseCurrentWeek(release.season);
  const db = legacyDb;
  const rows = await db
    .select({
      season: schema.currentWeek.season,
      week: schema.currentWeek.week,
      updatedAt: schema.currentWeek.updatedAt,
      activeRunId: schema.currentWeek.activeRunId,
    })
    .from(schema.currentWeek)
    .where(eq(schema.currentWeek.id, 1))
    .limit(1);
  const row = rows[0];
  if (!row || (row.season === 0 && row.week === 0)) return null;
  return { season: row.season, week: row.week, updatedAt: row.updatedAt, activeRunId: row.activeRunId };
});

export type RunSummary = {
  runId: string;
  modelId: string;
  state: "preview" | "published" | "frozen" | "scored";
  evidenceClass: "legacy" | "pending" | "replay" | "live" | "missed";
  createdAt: Date;
  expectedGames: number;
  predictedGames: number;
  linedGames: number;
  /** Generated during its week, partial slate, never prospective (Contract 04, Amendment 9). */
  displayOnly: boolean;
};

/**
 * One explicitly selected public run; missing selection never guesses. The
 * selected run may be V5 or an eligible legacy V4 rollback (same slate),
 * so eligibility is validated after the join rather than filtered to V5.
 */
export const getRunForWeek = cache(releaseCached("getRunForWeek", async (season: number, week: number): Promise<RunSummary | null> => {
  const db = await getSeasonDb(season);
  const rows = await db.select({
    runId: schema.predictionRuns.runId,
    modelId: schema.predictionRuns.modelId,
    state: schema.predictionRuns.state,
    evidenceClass: schema.predictionRuns.evidenceClass,
    createdAt: schema.predictionRuns.createdAt,
    expectedGames: schema.predictionRuns.expectedGames,
    predictedGames: schema.predictionRuns.predictedGames,
    linedGames: schema.predictionRuns.linedGames,
    validation: schema.predictionRuns.validation,
  })
    .from(schema.siteWeekSelections)
    .innerJoin(schema.predictionRuns, eq(schema.siteWeekSelections.runId, schema.predictionRuns.runId))
    .where(and(
      eq(schema.siteWeekSelections.season, season),
      eq(schema.siteWeekSelections.week, week),
      eq(schema.predictionRuns.season, season),
      eq(schema.predictionRuns.week, week),
    ))
    .limit(1);
  const row = rows[0];
  if (!row || !isSelectableRun(row)) return null;
  return {
    runId: row.runId,
    modelId: row.modelId ?? "",
    state: row.state as RunSummary["state"],
    evidenceClass: row.evidenceClass as RunSummary["evidenceClass"],
    createdAt: row.createdAt,
    expectedGames: row.expectedGames,
    predictedGames: row.predictedGames,
    linedGames: row.linedGames,
    displayOnly: isDisplayOnly(row.validation),
  };
}, RUN_STATE_CACHE));

/** Distinct weeks with published games for a season, ascending. Used by the week nav. */
export const getAvailableWeeks = releaseCached("getAvailableWeeks", async (season: number): Promise<number[]> => {
  const db = await getSeasonDb(season);
  const rows = await db.select({
    week: schema.siteWeekSelections.week,
    modelId: schema.predictionRuns.modelId,
    state: schema.predictionRuns.state,
    evidenceClass: schema.predictionRuns.evidenceClass,
  })
    .from(schema.siteWeekSelections)
    .innerJoin(schema.predictionRuns, eq(schema.siteWeekSelections.runId, schema.predictionRuns.runId))
    .where(eq(schema.siteWeekSelections.season, season))
    .orderBy(asc(schema.siteWeekSelections.week));
  return rows.filter(isSelectableRun).map((row) => row.week);
}, RUN_STATE_CACHE);

/**
 * Distinct weeks with completed/scored games for a season, ascending: scored
 * selected runs, plus published display-only runs whose games have finals.
 */
export const getScoredWeeks = cache(releaseCached("getScoredWeeks", async (season: number): Promise<number[]> => {
  if (process.env.CFB_UI_TEST_MODE === "1") {
    return [0, 1, 2];
  }
  const db = await getSeasonDb(season);
  const rows = await db.select({
    week: schema.siteWeekSelections.week,
    modelId: schema.predictionRuns.modelId,
    state: schema.predictionRuns.state,
    evidenceClass: schema.predictionRuns.evidenceClass,
    validation: schema.predictionRuns.validation,
    gradedGames: sql<number>`(
      SELECT count(*) FROM predictions p
      JOIN game_results gr ON gr.game_id = p.game_id
      WHERE p.run_id = ${schema.predictionRuns.runId}
    )`.mapWith(Number),
  })
    .from(schema.siteWeekSelections)
    .innerJoin(schema.predictionRuns, eq(schema.siteWeekSelections.runId, schema.predictionRuns.runId))
    .where(and(
      eq(schema.siteWeekSelections.season, season),
      inArray(schema.predictionRuns.state, ["published", "scored"]),
    ));
  return selectGradedWeeks(rows);
}, RUN_STATE_CACHE));

/** Distinct upcoming/unscored weeks with published forecasts for a season, ascending. */
export const getUpcomingWeeks = releaseCached("getUpcomingWeeks", async (season: number): Promise<number[]> => {
  if (process.env.CFB_UI_TEST_MODE === "1") {
    return [0];
  }
  const db = await getSeasonDb(season);
  const rows = await db.select({
    week: schema.siteWeekSelections.week,
    modelId: schema.predictionRuns.modelId,
    state: schema.predictionRuns.state,
    evidenceClass: schema.predictionRuns.evidenceClass,
  })
    .from(schema.siteWeekSelections)
    .innerJoin(schema.predictionRuns, eq(schema.siteWeekSelections.runId, schema.predictionRuns.runId))
    .where(and(
      eq(schema.siteWeekSelections.season, season),
      inArray(schema.predictionRuns.state, ["published", "frozen"]),
    ))
    .orderBy(asc(schema.siteWeekSelections.week));
  return rows.filter(isSelectableRun).map((row) => row.week);
}, RUN_STATE_CACHE);

type CompletedGameRow = {
  startDate: Date;
  homeTeam: string;
  awayTeam: string;
  homePoints: number;
  awayPoints: number;
};

/**
 * Completed season games in kickoff order. Card views advance through this
 * timeline to snapshot each team's record as of a game's kickoff, so
 * historical week pages never leak later results.
 */
const getSeasonCompletedGames = cache(releaseCached("getSeasonCompletedGames", async (season: number): Promise<CompletedGameRow[]> => {
  const db = await getSeasonDb(season);
  const rows = await db
    .select({
      startDate: schema.games.startDate,
      homeTeam: schema.games.homeTeam,
      awayTeam: schema.games.awayTeam,
      homePoints: schema.gameResults.homePoints,
      awayPoints: schema.gameResults.awayPoints,
    })
    .from(schema.games)
    .innerJoin(
      schema.gameResults,
      eq(schema.games.gameId, schema.gameResults.gameId),
    )
    .where(
      and(
        eq(schema.games.season, season),
        eq(schema.gameResults.completionState, "completed"),
      ),
    )
    .orderBy(asc(schema.games.startDate), asc(schema.games.gameId));
  return rows.filter(
    (row): row is CompletedGameRow =>
      row.homePoints !== null && row.awayPoints !== null,
  );
}));

function recordLabel(record: { wins: number; losses: number } | undefined): string | null {
  if (!record || record.wins + record.losses === 0) return null;
  return `${record.wins}-${record.losses}`;
}

/**
 * Attach point-in-time season records to a week's games (either publication
 * mode). Precondition: `games` is in kickoff order (all query paths order by
 * startDate). Strictly-earlier completions count, so a game's own final never
 * appears in its own record.
 */
function withRecords<
  T extends { startDate: Date; homeTeam: string; awayTeam: string },
>(games: T[], completed: CompletedGameRow[]): (T & {
  homeRecord: string | null;
  awayRecord: string | null;
})[] {
  const records = new Map<string, { wins: number; losses: number }>();
  const bump = (team: string) => {
    const entry = records.get(team) ?? { wins: 0, losses: 0 };
    records.set(team, entry);
    return entry;
  };
  let cursor = 0;
  return games.map((game) => {
    const kickoff = game.startDate.getTime();
    while (cursor < completed.length && completed[cursor].startDate.getTime() < kickoff) {
      const { homeTeam, awayTeam, homePoints, awayPoints } = completed[cursor];
      const winner = homePoints > awayPoints ? homeTeam : awayPoints > homePoints ? awayTeam : null;
      const loser = homePoints > awayPoints ? awayTeam : awayPoints > homePoints ? homeTeam : null;
      if (winner && loser) {
        bump(winner).wins += 1;
        bump(loser).losses += 1;
      }
      cursor += 1;
    }
    return {
      ...game,
      homeRecord: recordLabel(records.get(game.homeTeam)),
      awayRecord: recordLabel(records.get(game.awayTeam)),
    };
  });
}

type FrozenLine = { spread: number | null; total: number | null };

/**
 * Frozen pre-kickoff snapshot lines from each week's closed non-V5 run, for several weeks
 * in two queries (runs, then their snapshot lines) instead of one per run per week. Within
 * a week, scored runs win over frozen ones and the first run that has snapshot lines is used.
 */
async function frozenLinesForWeeks(
  season: number,
  weeks: number[],
): Promise<Map<number, Map<number, FrozenLine>>> {
  const byWeek = new Map<number, Map<number, FrozenLine>>(weeks.map((week) => [week, new Map()]));
  if (weeks.length === 0) return byWeek;
  const db = await getSeasonDb(season);
  const runs = await db
    .select({
      runId: schema.predictionRuns.runId,
      week: schema.predictionRuns.week,
      state: schema.predictionRuns.state,
    })
    .from(schema.predictionRuns)
    .where(
      and(
        eq(schema.predictionRuns.season, season),
        inArray(schema.predictionRuns.week, weeks),
        notLike(schema.predictionRuns.modelId, "v5-%"),
        inArray(schema.predictionRuns.state, ["frozen", "scored"]),
      ),
    );
  if (runs.length === 0) return byWeek;
  const snapshotRows = await db
    .select({
      runId: schema.predictions.runId,
      gameId: schema.predictions.gameId,
      spread: schema.marketSnapshots.spread,
      total: schema.marketSnapshots.total,
    })
    .from(schema.predictions)
    .innerJoin(
      schema.marketSnapshots,
      eq(schema.predictions.marketSnapshotId, schema.marketSnapshots.snapshotId),
    )
    .where(inArray(schema.predictions.runId, runs.map((run) => run.runId)));
  const linesByRun = new Map<string, Map<number, FrozenLine>>();
  for (const row of snapshotRows) {
    const lines = linesByRun.get(row.runId) ?? new Map<number, FrozenLine>();
    linesByRun.set(row.runId, lines);
    if (!lines.has(row.gameId)) lines.set(row.gameId, { spread: row.spread, total: row.total });
  }
  for (const week of weeks) {
    const ordered = runs
      .filter((run) => run.week === week)
      .sort((a, b) => (a.state === b.state ? 0 : a.state === "scored" ? -1 : 1));
    for (const run of ordered) {
      const lines = linesByRun.get(run.runId);
      if (lines && lines.size > 0) {
        byWeek.set(week, lines);
        break;
      }
    }
  }
  return byWeek;
}

type FrozenLineFields = {
  gameId: number;
  homeTeamSpreadLine: number | null;
  totalLine: number | null;
  predictedSpread: number | null;
  predictedTotal: number | null;
  spreadLean: "home" | "away" | null;
  totalLean: "over" | "under" | null;
  edgeSpread: number | null;
  edgeTotal: number | null;
};

const missesLines = (rows: FrozenLineFields[]) =>
  rows.some((row) => row.homeTeamSpreadLine === null || row.totalLine === null);

/**
 * Fill market lines missing from serv­ing rows (replay runs are built without
 * a market feed) from the week's frozen snapshots — the same quotes the
 * grades use — and derive the matching leans and edges. Stored values are
 * never overwritten; the immutable prediction bytes are untouched.
 */
function applyFrozenLines<T extends FrozenLineFields>(rows: T[], lines: Map<number, FrozenLine>): T[] {
  if (lines.size === 0) return rows;
  return rows.map((row) => {
    const frozen = lines.get(row.gameId);
    if (!frozen) return row;
    const homeTeamSpreadLine = row.homeTeamSpreadLine ?? frozen.spread;
    const totalLine = row.totalLine ?? frozen.total;
    let { spreadLean, totalLean, edgeSpread, edgeTotal } = row;
    if (spreadLean === null) {
      const view = deriveSpreadView(row.predictedSpread, homeTeamSpreadLine);
      spreadLean = view.lean;
      if (edgeSpread === null) edgeSpread = view.edge;
    }
    if (totalLean === null) {
      const view = deriveTotalView(row.predictedTotal, totalLine);
      totalLean = view.lean;
      if (edgeTotal === null) edgeTotal = view.edge;
    }
    return { ...row, homeTeamSpreadLine, totalLine, spreadLean, totalLean, edgeSpread, edgeTotal };
  });
}

export async function withFrozenLines<T extends FrozenLineFields>(rows: T[], season: number, week: number): Promise<T[]> {
  if (!missesLines(rows)) return rows;
  return applyFrozenLines(rows, (await frozenLinesForWeeks(season, [week])).get(week) ?? new Map());
}

type TargetSelection = {
  point: number;
  side: string;
  edge: number | null;
  /** Provider (sportsbook) of the selected quote. */
  source: string | null;
};

type GameSelections = {
  spread?: TargetSelection;
  total?: TargetSelection;
};

/**
 * Check whether prediction_market_selections table exists in the current database.
 * Cached to avoid querying the catalog repeatedly.
 */
export const hasSelectionsTable = cache(async (season = publicationScope.season): Promise<boolean> => {
  if (await getSeasonReleaseContext(season)) return true;
  try {
    const res = await legacyDb.execute(
      sql`SELECT to_regclass('public.prediction_market_selections') IS NOT NULL AS exists`
    );
    return existsFrom(res);
  } catch {
    return false;
  }
});

/**
 * Fetch target-level market selections for several runs in one query, if the
 * table exists. Returns empty maps if unmigrated or no selections exist.
 */
export async function getMarketSelectionsForRuns(
  runIds: string[],
  season = publicationScope.season,
  strict = false,
): Promise<Map<string, Map<number, GameSelections>>> {
  const byRun = new Map<string, Map<number, GameSelections>>(
    runIds.map((runId) => [runId, new Map()]),
  );
  if (runIds.length === 0) return byRun;
  const db = await getSeasonDb(season);
  const tableExists = await hasSelectionsTable(season);
  if (!tableExists) return byRun;

  try {
    const selections = await db
      .select({
        runId: schema.predictionMarketSelections.runId,
        gameId: schema.predictionMarketSelections.gameId,
        target: schema.predictionMarketSelections.target,
        side: schema.predictionMarketSelections.side,
        point: schema.predictionMarketSelections.point,
        edge: schema.predictionMarketSelections.edge,
        // Left join: a missing quote must never change which lines are served.
        source: schema.marketQuotes.provider,
      })
      .from(schema.predictionMarketSelections)
      .leftJoin(
        schema.marketQuotes,
        eq(schema.predictionMarketSelections.quoteId, schema.marketQuotes.quoteId),
      )
      .where(inArray(schema.predictionMarketSelections.runId, runIds));

    for (const sel of selections) {
      const map = byRun.get(sel.runId);
      if (!map || (sel.target !== "spread" && sel.target !== "total")) continue;
      const entry = map.get(sel.gameId) ?? {};
      map.set(sel.gameId, entry);
      entry[sel.target] = {
        point: sel.point,
        side: sel.side,
        edge: sel.edge,
        source: sel.source ?? null,
      };
    }
    return byRun;
  } catch (error) {
    if (strict) throw new SwallowedReadError(error);
    return new Map(runIds.map((runId) => [runId, new Map()]));
  }
}

/** Target-level market selections for one run; see `getMarketSelectionsForRuns`. */
export async function getMarketSelectionsForRun(
  runId: string,
  season = publicationScope.season,
  strict = false,
): Promise<Map<number, GameSelections>> {
  return (await getMarketSelectionsForRuns([runId], season, strict)).get(runId) ?? new Map();
}

/**
 * Whether the game_venues table exists. Cached; false before migration 0019 is
 * applied, so the site keeps working and simply shows no location.
 */
export const hasGameVenuesTable = cache(async (season = publicationScope.season): Promise<boolean> => {
  if (await getSeasonReleaseContext(season)) return true;
  try {
    const res = await legacyDb.execute(
      sql`SELECT to_regclass('public.game_venues') IS NOT NULL AS exists`,
    );
    return existsFrom(res);
  } catch {
    return false;
  }
});

/** Whether team_season_stats exists. Cached; false before migration 0020 is applied. */
export const hasTeamSeasonStatsTable = cache(async (season = publicationScope.season): Promise<boolean> => {
  if (await getSeasonReleaseContext(season)) return true;
  try {
    const res = await legacyDb.execute(
      sql`SELECT to_regclass('public.team_season_stats') IS NOT NULL AS exists`,
    );
    return existsFrom(res);
  } catch {
    return false;
  }
});

/**
 * Pre-game stats snapshot (games completed before `asOfWeek`) for the given teams.
 * Never throws; returns [] when the table or rows are missing.
 */
const queryTeamSeasonStats = releaseCached("getTeamSeasonStats", async (
  season: number,
  asOfWeek: number,
  teams: string[],
): Promise<TeamStatRow[]> => {
  const db = await getSeasonDb(season);
  const t = schema.teamSeasonStats;
  const rows = await db
    .select({
      team: t.team,
      role: t.role,
      metric: t.metric,
      value: t.value,
      n: t.n,
      games: t.games,
      rank: t.rank,
      cohortSize: t.cohortSize,
      // Ties share the minimum rank, so a tie is another team with the same rank.
      tied: sql<boolean>`${sql.raw(tiedExistsSql("team_season_stats"))}`,
    })
    .from(t)
    .where(and(eq(t.season, season), eq(t.asOfWeek, asOfWeek), inArray(t.team, teams)));
  guardRows("team_season_stats", rows, TEAM_STAT_SPEC, TEAM_STAT_RULES);
  return rows.map((r) => ({
    team: r.team,
    role: r.role === "defense" ? "defense" : "offense",
    metric: r.metric,
    value: r.value,
    n: r.n,
    games: r.games,
    rank: r.rank,
    cohortSize: r.cohortSize,
    tied: Boolean(r.tied),
  }));
});

export async function getTeamSeasonStats(
  season: number,
  asOfWeek: number,
  teams: string[],
): Promise<TeamStatRow[]> {
  await getSeasonDb(season);
  if (teams.length === 0 || !(await hasTeamSeasonStatsTable(season))) return [];
  try {
    return await queryTeamSeasonStats(season, asOfWeek, teams);
  } catch (error) {
    // A contract violation is not "no stats": let the caller show an unavailable state.
    if (error instanceof RowContractError) throw error;
    return [];
  }
}

/** Whether team_possession_stats exists. Cached; false before migration 0021 is applied. */
export const hasTeamPossessionStatsTable = cache(async (season = publicationScope.season): Promise<boolean> => {
  if (await getSeasonReleaseContext(season)) return true;
  try {
    const res = await legacyDb.execute(
      sql`SELECT to_regclass('public.team_possession_stats') IS NOT NULL AS exists`,
    );
    return existsFrom(res);
  } catch {
    return false;
  }
});

/**
 * RAW V5 possession metrics (points, EPA and plays per possession, non-offense
 * points) as of `asOfWeek`. Selects raw columns from the raw table only: the
 * opponent-adjusted values live in their own table and are never read here.
 * Never throws; returns [] when the table or rows are missing.
 */
const queryTeamPossessionStats = releaseCached("getTeamPossessionStats", async (
  season: number,
  asOfWeek: number,
  teams: string[],
): Promise<TeamStatRow[]> => {
  const db = await getSeasonDb(season);
  const t = schema.teamPossessionStats;
  const rows = await db
    .select({
      team: t.team,
      role: t.role,
      metric: t.metric,
      value: t.value,
      n: t.n,
      games: t.games,
      rank: t.rank,
      cohortSize: t.cohortSize,
      tied: sql<boolean>`${sql.raw(tiedExistsSql("team_possession_stats"))}`,
    })
    .from(t)
    .where(and(eq(t.season, season), eq(t.asOfWeek, asOfWeek), inArray(t.team, teams)));
  guardRows("team_possession_stats", rows, TEAM_STAT_SPEC, TEAM_STAT_RULES);
  return rows.map((r) => ({
    team: r.team,
    role: r.role === "defense" ? "defense" : "offense",
    metric: r.metric,
    value: r.value,
    n: r.n,
    games: r.games,
    rank: r.rank,
    cohortSize: r.cohortSize,
    tied: Boolean(r.tied),
  }));
});

export async function getTeamPossessionStats(
  season: number,
  asOfWeek: number,
  teams: string[],
): Promise<TeamStatRow[]> {
  await getSeasonDb(season);
  if (teams.length === 0 || !(await hasTeamPossessionStatsTable(season))) return [];
  try {
    return await queryTeamPossessionStats(season, asOfWeek, teams);
  } catch (error) {
    // A contract violation is not "no stats": let the caller show an unavailable state.
    if (error instanceof RowContractError) throw error;
    return [];
  }
}

/** Attach venue city/state/neutral-site to games. Never throws; missing data stays null. */
async function withVenues<T extends { gameId: number }>(
  games: T[],
  season: number,
  strict = false,
): Promise<(T & { venueCity: string | null; venueState: string | null; neutralSite: boolean | null })[]> {
  const db = await getSeasonDb(season);
  const empty = games.map((g) => ({ ...g, venueCity: null, venueState: null, neutralSite: null }));
  if (games.length === 0 || !(await hasGameVenuesTable(season))) return empty;
  try {
    const rows = await db
      .select({
        gameId: schema.gameVenues.gameId,
        city: schema.gameVenues.city,
        state: schema.gameVenues.state,
        neutralSite: schema.gameVenues.neutralSite,
      })
      .from(schema.gameVenues)
      .where(inArray(schema.gameVenues.gameId, games.map((g) => g.gameId)));
    const byGame = new Map(rows.map((r) => [r.gameId, r]));
    return games.map((g) => {
      const v = byGame.get(g.gameId);
      return {
        ...g,
        venueCity: v?.city ?? null,
        venueState: v?.state ?? null,
        neutralSite: v?.neutralSite ?? null,
      };
    });
  } catch (error) {
    if (strict) throw new SwallowedReadError(error);
    return empty;
  }
}

/**
 * Return all games (with optional results) for a given season/week, sorted by start time.
 * Cached per release (the run state it carries is capped at an hour); optional venue and
 * selection failures are never cached, see `cachedOrTolerant`.
 */
async function loadGamesForWeek(season: number, week: number, strict: boolean): Promise<Game[]> {
  const db = await getSeasonDb(season);
  const run = await getRunForWeek(season, week);
  if (run) {
    const [rows, selectionsMap, completed] = await Promise.all([
      db
        .select({
          runId: schema.predictions.runId,
          gameId: schema.games.gameId,
          season: schema.games.season,
          week: schema.games.week,
          startDate: schema.games.startDate,
          homeTeam: schema.games.homeTeam,
          awayTeam: schema.games.awayTeam,
          homeTeamSpreadLine: schema.predictions.homeTeamSpreadLine,
          totalLine: schema.predictions.totalLine,
          predictedSpread: schema.predictions.predictedSpread,
          predictedTotal: schema.predictions.predictedTotal,
          predictedSpreadStdDev: schema.predictions.predictedSpreadStdDev,
          predictedTotalStdDev: schema.predictions.predictedTotalStdDev,
          spreadLean: schema.predictions.spreadLean,
          totalLean: schema.predictions.totalLean,
          edgeSpread: schema.predictions.edgeSpread,
          edgeTotal: schema.predictions.edgeTotal,
          highConfidence: schema.predictions.highConfidence,
          regime: schema.predictions.regime,
          homeCompletedGames: schema.predictions.homeCompletedGames,
          awayCompletedGames: schema.predictions.awayCompletedGames,
          spreadModelVersion: schema.predictions.spreadModelVersion,
          totalModelVersion: schema.predictions.totalModelVersion,
          systemName: schema.predictionRuns.systemName,
          modelId: schema.predictionRuns.modelId,
          updatedAt: schema.predictionRuns.createdAt,
          homePoints: schema.gameResults.homePoints,
          awayPoints: schema.gameResults.awayPoints,
          spreadResult: sql<"win" | "loss" | "push" | null>`(
            SELECT pg.result FROM prediction_grades pg
            WHERE pg.run_id = ${schema.predictions.runId}
              AND pg.game_id = ${schema.predictions.gameId}
              AND pg.target = 'spread'
            LIMIT 1
          )`,
          totalResult: sql<"win" | "loss" | "push" | null>`(
            SELECT pg.result FROM prediction_grades pg
            WHERE pg.run_id = ${schema.predictions.runId}
              AND pg.game_id = ${schema.predictions.gameId}
              AND pg.target = 'total'
            LIMIT 1
          )`,
        })
        .from(schema.predictions)
        .innerJoin(schema.games, eq(schema.predictions.gameId, schema.games.gameId))
        .innerJoin(schema.predictionRuns, eq(schema.predictions.runId, schema.predictionRuns.runId))
        .leftJoin(schema.gameResults, eq(schema.games.gameId, schema.gameResults.gameId))
        .where(eq(schema.predictions.runId, run.runId))
        .orderBy(asc(schema.games.startDate), asc(schema.games.gameId)),
      getMarketSelectionsForRun(run.runId, season, strict),
      getSeasonCompletedGames(season),
    ]);

    guardRows("games_for_week", rows, PREDICTION_GAME_SPEC);
    const rowsWithSelections = rows.map((row) =>
      overlaySelection(row, selectionsMap.get(row.gameId)),
    );

    // Venues and frozen-line fallbacks are independent of each other.
    const [withVenue, frozenLines] = await Promise.all([
      withVenues(rowsWithSelections, season, strict),
      missesLines(rowsWithSelections)
        ? frozenLinesForWeeks(season, [week]).then((byWeek) => byWeek.get(week) ?? new Map<number, FrozenLine>())
        : Promise.resolve(new Map<number, FrozenLine>()),
    ]);
    const games = applyFrozenLines(
      withVenue.map((row) => ({
        ...row,
        publicationMode: "predictions" as const,
        runState: run.state,
        evidenceClass: run.evidenceClass,
      })),
      frozenLines,
    );
    return withRecords(games, completed) as PredictionGame[];
  }

  if (season === 2026) return loadMarketGamesForWeek(season, week, strict);

  // Temporary compatibility path for rows published before run versioning.
  const rows = await db
    .select({
      gameId: schema.games.gameId,
      season: schema.games.season,
      week: schema.games.week,
      startDate: schema.games.startDate,
      homeTeam: schema.games.homeTeam,
      awayTeam: schema.games.awayTeam,
      homeTeamSpreadLine: schema.games.homeTeamSpreadLine,
      totalLine: schema.games.totalLine,
      predictedSpread: schema.games.predictedSpread,
      predictedTotal: schema.games.predictedTotal,
      predictedSpreadStdDev: schema.games.predictedSpreadStdDev,
      predictedTotalStdDev: schema.games.predictedTotalStdDev,
      spreadLean: schema.games.spreadLean,
      totalLean: schema.games.totalLean,
      edgeSpread: schema.games.edgeSpread,
      edgeTotal: schema.games.edgeTotal,
      highConfidence: schema.games.highConfidence,
      systemName: schema.games.systemName,
      modelId: schema.games.modelId,
      updatedAt: schema.games.updatedAt,
      // Results (nullable until scored)
      homePoints: schema.gameResults.homePoints,
      awayPoints: schema.gameResults.awayPoints,
      spreadResult: schema.gameResults.spreadResult,
      totalResult: schema.gameResults.totalResult,
    })
    .from(schema.games)
    .leftJoin(
      schema.gameResults,
      eq(schema.games.gameId, schema.gameResults.gameId),
    )
    .where(
      and(
        eq(schema.games.season, season),
        eq(schema.games.week, week),
      ),
    )
    .orderBy(asc(schema.games.startDate), asc(schema.games.gameId));
  const completed = await getSeasonCompletedGames(season);
  return withRecords(
    rows.map((row) => ({
      ...row,
      publicationMode: "predictions" as const,
      runId: null,
      runState: "legacy" as const,
      regime: null,
      homeCompletedGames: 0,
      awayCompletedGames: 0,
      spreadModelVersion: null,
      totalModelVersion: null,
    })),
    completed,
  ) as PredictionGame[];
}

const cachedGamesForWeek = releaseCached("getGamesForWeek", (season: number, week: number) =>
  loadGamesForWeek(season, week, true), RUN_STATE_CACHE);

export const getGamesForWeek = (season: number, week: number): Promise<Game[]> =>
  cachedOrTolerant(cachedGamesForWeek, (s: number, w: number) => loadGamesForWeek(s, w, false), season, week);

/** Schedule + current published market lines without selecting model output. */
async function loadMarketGamesForWeek(
  season: number,
  week: number,
  strict: boolean,
): Promise<MarketGame[]> {
  const db = await getSeasonDb(season);
  // A settled grade is safe to disclose, but it must remain tied to the exact
  // versioned run selected for this week. Legacy rows have no run identity.
  const [run, completed] = await Promise.all([getRunForWeek(season, week), getSeasonCompletedGames(season)]);
  const spreadResult = run
    ? sql<"win" | "loss" | "push" | null>`(
        SELECT pg.result FROM prediction_grades pg
        WHERE pg.run_id = ${run.runId}
          AND pg.game_id = ${schema.games.gameId}
          AND pg.target = 'spread'
        LIMIT 1
      )`
    : season === 2026 ? sql<"win" | "loss" | "push" | null>`NULL` : schema.gameResults.spreadResult;
  const totalResult = run
    ? sql<"win" | "loss" | "push" | null>`(
        SELECT pg.result FROM prediction_grades pg
        WHERE pg.run_id = ${run.runId}
          AND pg.game_id = ${schema.games.gameId}
          AND pg.target = 'total'
        LIMIT 1
      )`
    : season === 2026 ? sql<"win" | "loss" | "push" | null>`NULL` : schema.gameResults.totalResult;
  const rows = await db
    .select({
      gameId: schema.games.gameId,
      season: schema.games.season,
      week: schema.games.week,
      startDate: schema.games.startDate,
      homeTeam: schema.games.homeTeam,
      awayTeam: schema.games.awayTeam,
      homeTeamSpreadLine: schema.games.homeTeamSpreadLine,
      totalLine: schema.games.totalLine,
      updatedAt: schema.games.updatedAt,
      homePoints: schema.gameResults.homePoints,
      awayPoints: schema.gameResults.awayPoints,
      spreadResult,
      totalResult,
    })
    .from(schema.games)
    .leftJoin(schema.gameResults, eq(schema.games.gameId, schema.gameResults.gameId))
    .where(and(eq(schema.games.season, season), eq(schema.games.week, week)))
    .orderBy(asc(schema.games.startDate), asc(schema.games.gameId));

  return withRecords(
    (await withVenues(rows, season, strict)).map((row) => ({ ...row, publicationMode: "market" as const })),
    completed,
  );
}

const cachedMarketGamesForWeek = releaseCached("getMarketGamesForWeek", (season: number, week: number) =>
  loadMarketGamesForWeek(season, week, true), RUN_STATE_CACHE);

export const getMarketGamesForWeek = (season: number, week: number): Promise<MarketGame[]> =>
  cachedOrTolerant(cachedMarketGamesForWeek, (s: number, w: number) => loadMarketGamesForWeek(s, w, false), season, week);

function emptyStats(season: number): Stats {
  return {
    season,
    asOfWeek: null,
    spreadWins: 0,
    spreadLosses: 0,
    spreadPushes: 0,
    totalWins: 0,
    totalLosses: 0,
    totalPushes: 0,
  };
}

/**
 * Immutable W-L-P snapshot through a selected week. A replacement run can be
 * published during the week, but only the latest scored run is authoritative
 * once grades are available, including selected pending runs. This intentionally does not read `system_stats`:
 * that table is the latest full-season aggregate maintained by the pipeline.
 */
export const getSystemStatsThroughWeek = cache(releaseCached("getSystemStatsThroughWeek", async (
  season: number,
  throughWeek: number,
): Promise<Stats> => {
  const db = await getSeasonDb(season);
  const candidates = await db
    .select({
      runId: schema.predictionRuns.runId,
      week: schema.predictionRuns.week,
    })
    .from(schema.siteWeekSelections)
    .innerJoin(schema.predictionRuns, eq(schema.siteWeekSelections.runId, schema.predictionRuns.runId))
    .where(
      and(
        eq(schema.siteWeekSelections.season, season),
        lte(schema.siteWeekSelections.week, throughWeek),
        inArray(schema.predictionRuns.state, ["published", "frozen", "scored"]),
        or(
          inArray(schema.predictionRuns.evidenceClass, [...V5_RECORD_EVIDENCE]),
          eq(schema.predictionRuns.evidenceClass, "legacy"),
        ),
      ),
    )
    .orderBy(asc(schema.siteWeekSelections.week));

  const selectedWeeks = new Map<number, string>();
  for (const candidate of candidates) {
    if (!selectedWeeks.has(candidate.week)) {
      selectedWeeks.set(candidate.week, candidate.runId);
    }
  }
  const runIds = [...selectedWeeks.values()];
  if (runIds.length === 0) return emptyStats(season);

  const grades = await db
    .select({
      runId: schema.predictionGrades.runId,
      target: schema.predictionGrades.target,
      result: schema.predictionGrades.result,
    })
    .from(schema.predictionGrades)
    .where(inArray(schema.predictionGrades.runId, runIds));

  if (grades.length === 0) return emptyStats(season);

  const stats = emptyStats(season);
  let asOfWeek: number | null = null;
  const weekByRunId = new Map(
    [...selectedWeeks.entries()].map(([week, runId]) => [runId, week]),
  );
  for (const grade of grades) {
    const week = weekByRunId.get(grade.runId);
    if (week !== undefined) {
      asOfWeek = asOfWeek === null ? week : Math.max(asOfWeek, week);
    }
    if (grade.target === "spread") {
      if (grade.result === "win") stats.spreadWins += 1;
      if (grade.result === "loss") stats.spreadLosses += 1;
      if (grade.result === "push") stats.spreadPushes += 1;
    }
    if (grade.target === "total") {
      if (grade.result === "win") stats.totalWins += 1;
      if (grade.result === "loss") stats.totalLosses += 1;
      if (grade.result === "push") stats.totalPushes += 1;
    }
  }
  return { ...stats, asOfWeek };
}, RUN_STATE_CACHE));

/**
 * Read only the pinned, diagnostic-only V4 historical context. A missing or
 * ambiguous serving projection fails closed rather than selecting a row.
 */
export const getHistoricalModelContext = cache(async (
  comparisonSeason: number,
  selectedWeek: number,
): Promise<HistoricalModelContext | null> => {
  const db = legacyDb;
  const rows = await db
    .select()
    .from(schema.historicalModelContext)
    .where(and(
      eq(schema.historicalModelContext.comparisonSeason, comparisonSeason),
      eq(schema.historicalModelContext.modelId, "week0-2026-v4-strict-20260818-r2"),
      eq(schema.historicalModelContext.calculationVersion, "v1"),
      eq(schema.historicalModelContext.timingClass, "historically_reconstructed"),
      eq(schema.historicalModelContext.usage, "post_phase5_diagnostic_only"),
    ));
  const full = rows.filter((row) => row.periodScope === "season");
  const week = rows.filter(
    (row) => row.periodScope === "week" && row.comparisonWeek === selectedWeek,
  );
  if (full.length !== 1 || week.length > 1) return null;
  const map = (row: typeof rows[number]): HistoricalContextPeriod => ({
    comparisonSeason: row.comparisonSeason,
    comparisonWeek: row.comparisonWeek,
    spreadWins: row.spreadWins,
    spreadLosses: row.spreadLosses,
    spreadPushes: row.spreadPushes,
    spreadComparedGames: row.spreadComparedGames,
    totalWins: row.totalWins,
    totalLosses: row.totalLosses,
    totalPushes: row.totalPushes,
    totalComparedGames: row.totalComparedGames,
  });
  return { modelId: full[0].modelId, fullSeason: map(full[0]), matchingWeek: week[0] ? map(week[0]) : null };
});

/**
 * Season record of each scored week's largest-edge leans ("Biggest edges"): one
 * lightweight read of (week, game, target, edge, grade) over the selected runs,
 * ranked by `biggestEdgesRecord`. Lines, sides and edges go through the same
 * `overlaySelection` and `withFrozenLines` steps as the full slate, so the
 * record equals the one computed from every week's full games.
 */
async function loadBiggestEdgesRecord(season: number, strict: boolean): Promise<Tally> {
  const weeks = await getScoredWeeks(season);
  if (weeks.length === 0) return { win: 0, loss: 0, push: 0 };
  const db = await getSeasonDb(season);
  const grade = (target: "spread" | "total") => sql<"win" | "loss" | "push" | null>`(
    SELECT pg.result FROM prediction_grades pg
    WHERE pg.run_id = ${schema.predictions.runId}
      AND pg.game_id = ${schema.predictions.gameId}
      AND pg.target = ${target}
    LIMIT 1
  )`;
  const rows = await db
    .select({
      runId: schema.predictions.runId,
      week: schema.games.week,
      gameId: schema.games.gameId,
      startDate: schema.games.startDate,
      homeTeam: schema.games.homeTeam,
      awayTeam: schema.games.awayTeam,
      homeTeamSpreadLine: schema.predictions.homeTeamSpreadLine,
      totalLine: schema.predictions.totalLine,
      predictedSpread: schema.predictions.predictedSpread,
      predictedTotal: schema.predictions.predictedTotal,
      spreadLean: schema.predictions.spreadLean,
      totalLean: schema.predictions.totalLean,
      edgeSpread: schema.predictions.edgeSpread,
      edgeTotal: schema.predictions.edgeTotal,
      spreadResult: grade("spread"),
      totalResult: grade("total"),
      modelId: schema.predictionRuns.modelId,
      state: schema.predictionRuns.state,
      evidenceClass: schema.predictionRuns.evidenceClass,
    })
    .from(schema.siteWeekSelections)
    .innerJoin(schema.predictionRuns, and(
      eq(schema.siteWeekSelections.runId, schema.predictionRuns.runId),
      eq(schema.predictionRuns.season, season),
      eq(schema.predictionRuns.week, schema.siteWeekSelections.week),
    ))
    .innerJoin(schema.predictions, eq(schema.predictions.runId, schema.predictionRuns.runId))
    .innerJoin(schema.games, eq(schema.predictions.gameId, schema.games.gameId))
    .where(and(
      eq(schema.siteWeekSelections.season, season),
      inArray(schema.siteWeekSelections.week, weeks),
    ))
    .orderBy(asc(schema.games.startDate), asc(schema.games.gameId));

  const selectable = rows.filter(isSelectableRun);
  const selections = await getMarketSelectionsForRuns(
    [...new Set(selectable.map((row) => row.runId))],
    season,
    strict,
  );
  const weekRowsByWeek = new Map(weeks.map((week) => [
    week,
    selectable
      .filter((row) => row.week === week)
      .map((row) => overlaySelection(row, selections.get(row.runId)?.get(row.gameId))),
  ]));
  // One batched lookup for every week that lacks lines, instead of one per week.
  const frozenLines = await frozenLinesForWeeks(
    season,
    weeks.filter((week) => missesLines(weekRowsByWeek.get(week) ?? [])),
  );
  const lean: LeanGradeRow[] = [];
  for (const week of weeks) {
    const weekRows = weekRowsByWeek.get(week) ?? [];
    for (const row of applyFrozenLines(weekRows, frozenLines.get(week) ?? new Map())) {
      const source = { ...row, publicationMode: "predictions" as const };
      for (const kind of ["spread", "total"] as const) {
        const found = leanFor(source, kind);
        if (found) {
          lean.push({
            week,
            gameId: row.gameId,
            startMs: row.startDate.getTime(),
            kind,
            edge: found.edge,
            grade: kind === "spread" ? row.spreadResult : row.totalResult,
          });
        }
      }
    }
  }
  return biggestEdgesRecord(lean);
}

const cachedBiggestEdgesRecord = releaseCached("getBiggestEdgesRecord", (season: number) =>
  loadBiggestEdgesRecord(season, true), RUN_STATE_CACHE);

export const getBiggestEdgesRecord = cache((season: number): Promise<Tally> =>
  cachedOrTolerant(cachedBiggestEdgesRecord, (value: number) => loadBiggestEdgesRecord(value, false), season));
