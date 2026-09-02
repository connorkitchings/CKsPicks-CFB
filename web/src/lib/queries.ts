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
  /** Season W-L as of this game's kickoff (null before the first game). */
  homeRecord: string | null;
  awayRecord: string | null;
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
const getSeasonCompletedGames = cache(async (season: number): Promise<CompletedGameRow[]> => {
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
});

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
    const completed = await getSeasonCompletedGames(season);
    return withRecords(
      rows.map((row) => ({
        ...row,
        publicationMode: "predictions" as const,
        runState: run.state,
      })),
      completed,
    ) as PredictionGame[];
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

  const completed = await getSeasonCompletedGames(season);
  return withRecords(
    rows.map((row) => ({ ...row, publicationMode: "market" as const })),
    completed,
  );
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
