import { desc, eq, asc, and, inArray, sql } from "drizzle-orm";
import { cache } from "react";
import { db, schema } from "./db";

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
  regime: "preseason" | "one_game" | "two_games" | "three_games" | "game_1" | "game_2" | "game_3" | "game_4" | "established" | null;
  homeCompletedGames: number;
  awayCompletedGames: number;
  spreadModelVersion: string | null;
  totalModelVersion: string | null;
  spreadResult: "win" | "loss" | "push" | null;
  totalResult: "win" | "loss" | "push" | null;
};

export type Game = MarketGame | PredictionGame;

/** YTD system record shape. */
export type Stats = {
  season: number;
  asOfWeek: number;
  spreadWins: number;
  spreadLosses: number;
  spreadPushes: number;
  totalWins: number;
  totalLosses: number;
  totalPushes: number;
  updatedAt: Date;
};

/** Return the active { season, week, updatedAt } from the singleton current_week row. */
export const getCurrentWeek = cache(async (): Promise<{
  season: number;
  week: number;
  updatedAt: Date;
  activeRunId: string | null;
} | null> => {
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
  state: "preview" | "published" | "frozen" | "scored";
  createdAt: Date;
  expectedGames: number;
  predictedGames: number;
  linedGames: number;
};

/** Active run for the live week; latest immutable frozen/scored run historically. */
export const getRunForWeek = cache(async (season: number, week: number): Promise<RunSummary | null> => {
  const current = await getCurrentWeek();
  if (current?.season === season && current.week === week && current.activeRunId) {
    const rows = await db.select().from(schema.predictionRuns)
      .where(eq(schema.predictionRuns.runId, current.activeRunId)).limit(1);
    return (rows[0] as RunSummary | undefined) ?? null;
  }
  const rows = await db.select().from(schema.predictionRuns)
    .where(and(
      eq(schema.predictionRuns.season, season),
      eq(schema.predictionRuns.week, week),
      inArray(schema.predictionRuns.state, ["frozen", "scored"]),
    ))
    .orderBy(desc(schema.predictionRuns.createdAt)).limit(1);
  return (rows[0] as RunSummary | undefined) ?? null;
});

/** Distinct weeks with published games for a season, ascending. Used by the week nav. */
export async function getAvailableWeeks(season: number): Promise<number[]> {
  const [runRows, legacyRows, current] = await Promise.all([db
    .select({ week: schema.predictionRuns.week })
    .from(schema.predictionRuns)
    .where(and(
      eq(schema.predictionRuns.season, season),
      inArray(schema.predictionRuns.state, ["frozen", "scored"]),
    ))
    .groupBy(schema.predictionRuns.week), db
    .select({ week: schema.games.week })
    .from(schema.games)
    .where(eq(schema.games.season, season))
    .groupBy(schema.games.week)
    .orderBy(asc(schema.games.week)), getCurrentWeek()]);
  const weeks = [...runRows, ...legacyRows].map((r) => r.week);
  if (current?.season === season && current.activeRunId) weeks.push(current.week);
  return [...new Set(weeks)].sort((a, b) => a - b);
}

/** Return all games (with optional results) for a given season/week, sorted by start time. */
export async function getGamesForWeek(season: number, week: number): Promise<Game[]> {
  const run = await getRunForWeek(season, week);
  if (run) {
    const rows = await db
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
      .orderBy(asc(schema.games.startDate), asc(schema.games.gameId));
    return rows.map((row) => ({
      ...row,
      publicationMode: "predictions" as const,
      runState: run.state,
    })) as PredictionGame[];
  }

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
  return rows.map((row) => ({
    ...row,
    publicationMode: "predictions" as const,
    runId: null,
    runState: "legacy" as const,
    regime: null,
    homeCompletedGames: 0,
    awayCompletedGames: 0,
    spreadModelVersion: null,
    totalModelVersion: null,
  })) as PredictionGame[];
}

/** Schedule + current published market lines without selecting model output. */
export async function getMarketGamesForWeek(
  season: number,
  week: number,
): Promise<MarketGame[]> {
  // A settled grade is safe to disclose, but it must remain tied to the exact
  // versioned run selected for this week. Legacy rows have no run identity.
  const run = await getRunForWeek(season, week);
  const spreadResult = run
    ? sql<"win" | "loss" | "push" | null>`(
        SELECT pg.result FROM prediction_grades pg
        WHERE pg.run_id = ${run.runId}
          AND pg.game_id = ${schema.games.gameId}
          AND pg.target = 'spread'
        LIMIT 1
      )`
    : schema.gameResults.spreadResult;
  const totalResult = run
    ? sql<"win" | "loss" | "push" | null>`(
        SELECT pg.result FROM prediction_grades pg
        WHERE pg.run_id = ${run.runId}
          AND pg.game_id = ${schema.games.gameId}
          AND pg.target = 'total'
        LIMIT 1
      )`
    : schema.gameResults.totalResult;
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

  return rows.map((row) => ({ ...row, publicationMode: "market" as const }));
}

/** YTD system record for a season (win/loss/push for spreads and totals). */
export async function getSystemStats(season: number): Promise<Stats | null> {
  const rows = await db
    .select()
    .from(schema.systemStats)
    .where(eq(schema.systemStats.season, season))
    .limit(1);
  return (rows[0] as Stats | undefined) ?? null;
}
