import { desc, eq, asc, and } from "drizzle-orm";
import { db, schema } from "./db";

/** Shape of a game row returned by getGamesForWeek (prediction + optional result). */
export type Game = {
  gameId: number;
  season: number;
  week: number;
  startDate: Date;
  homeTeam: string;
  awayTeam: string;
  homeTeamSpreadLine: number | null;
  totalLine: number | null;
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
  updatedAt: Date;
  homePoints: number | null;
  awayPoints: number | null;
  spreadResult: "win" | "loss" | "push" | null;
  totalResult: "win" | "loss" | "push" | null;
};

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
export async function getCurrentWeek(): Promise<{
  season: number;
  week: number;
  updatedAt: Date;
} | null> {
  const rows = await db
    .select({
      season: schema.currentWeek.season,
      week: schema.currentWeek.week,
      updatedAt: schema.currentWeek.updatedAt,
    })
    .from(schema.currentWeek)
    .where(eq(schema.currentWeek.id, 1))
    .limit(1);
  const row = rows[0];
  if (!row || (row.season === 0 && row.week === 0)) return null;
  return { season: row.season, week: row.week, updatedAt: row.updatedAt };
}

/** Distinct weeks with published games for a season, ascending. Used by the week nav. */
export async function getAvailableWeeks(season: number): Promise<number[]> {
  const rows = await db
    .select({ week: schema.games.week })
    .from(schema.games)
    .where(eq(schema.games.season, season))
    .groupBy(schema.games.week)
    .orderBy(asc(schema.games.week));
  return rows.map((r) => r.week);
}

/** Return all games (with optional results) for a given season/week, sorted by start time. */
export async function getGamesForWeek(season: number, week: number): Promise<Game[]> {
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
  return rows as Game[];
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

/** Last N most-recent predictions across all weeks (for a small "recent leans" strip). */
export async function getRecentHighConfidenceGames(limit = 3): Promise<Game[]> {
  const rows = await db
    .select({
      gameId: schema.games.gameId,
      season: schema.games.season,
      week: schema.games.week,
      startDate: schema.games.startDate,
      homeTeam: schema.games.homeTeam,
      awayTeam: schema.games.awayTeam,
      spreadLean: schema.games.spreadLean,
      edgeSpread: schema.games.edgeSpread,
      spreadResult: schema.gameResults.spreadResult,
    })
    .from(schema.games)
    .leftJoin(
      schema.gameResults,
      eq(schema.games.gameId, schema.gameResults.gameId),
    )
    .where(eq(schema.games.highConfidence, true))
    .orderBy(desc(schema.games.startDate))
    .limit(limit);
  return rows as Game[];
}
