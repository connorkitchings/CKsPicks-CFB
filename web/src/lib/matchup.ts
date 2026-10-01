import { cache } from "react";
import { eq } from "drizzle-orm";
import { db, schema } from "./db.ts";
import { getCurrentRatings } from "./v5.ts";
import { displaySystemName } from "./publication.ts";
import {
  marketSpreadView,
  modelSpreadView,
  spreadLabel,
} from "./betting-format.ts";

export interface TeamMetricValue {
  value: number;
  rank: number;
  formatted: string;
}

export interface UnitMatchupRow {
  name: string;
  offenseValue: string;
  offenseRank: number;
  defenseValue: string;
  defenseRank: number;
}

export interface TeamProfileStats {
  team: string;
  rank: number | null;
  overallRating: number;
  offenseRating: number;
  defenseRating: number;
  record: string | null;
  epaMargin: TeamMetricValue;
  offEpa: TeamMetricValue;
  defEpa: TeamMetricValue;
  offSuccessRate: TeamMetricValue;
  offDropbackSr: TeamMetricValue;
  offRushSr: TeamMetricValue;
  defSuccessRate: TeamMetricValue;
  defDropbackSr: TeamMetricValue;
  defRushSr: TeamMetricValue;
  netPtsPerDrive: TeamMetricValue;
  offPtsPerDrive: TeamMetricValue;
  defPtsPerDrive: TeamMetricValue;
  netFieldPosition: TeamMetricValue;
  eckelRatio: TeamMetricValue;
}

export interface TeamRatingSummary {
  team: string;
  rank: number | null;
  overallRating: number;
  offenseRating: number;
  offenseRank: number | null;
  defenseRating: number;
  defenseRank: number | null;
}

export interface MatchupData {
  gameId: number;
  season: number;
  week: number;
  startDate: Date;
  homeTeam: string;
  awayTeam: string;
  systemName: string;
  modelId: string | null;
  publicationMode: "predictions" | "market";
  // Odds & Model
  marketSpread: string;
  modelSpread: string;
  marketTotal: number | null;
  modelTotal: number | null;
  spreadLean: "home" | "away" | null;
  totalLean: "over" | "under" | null;
  edgeSpread: number | null;
  edgeTotal: number | null;
  highConfidence: boolean;
  // Final results if game completed
  homeFinalPoints: number | null;
  awayFinalPoints: number | null;
  // Ratings
  awayRating: TeamRatingSummary;
  homeRating: TeamRatingSummary;
}

/**
 * Fetch and construct authentic matchup breakdown for a specific gameId.
 * Never produces synthetic or mocked statistical metrics.
 */
export const getMatchupData = cache(async (gameId: number): Promise<MatchupData | null> => {
  const gameRows = await db
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
      spreadLean: schema.games.spreadLean,
      totalLean: schema.games.totalLean,
      edgeSpread: schema.games.edgeSpread,
      edgeTotal: schema.games.edgeTotal,
      highConfidence: schema.games.highConfidence,
      systemName: schema.games.systemName,
      modelId: schema.games.modelId,
    })
    .from(schema.games)
    .where(eq(schema.games.gameId, gameId))
    .limit(1);

  if (gameRows.length === 0) return null;
  const game = gameRows[0];

  // Optional results
  const resultRows = await db
    .select({
      homePoints: schema.gameResults.homePoints,
      awayPoints: schema.gameResults.awayPoints,
    })
    .from(schema.gameResults)
    .where(eq(schema.gameResults.gameId, gameId))
    .limit(1);

  const homeFinalPoints = resultRows[0]?.homePoints ?? null;
  const awayFinalPoints = resultRows[0]?.awayPoints ?? null;

  // Real ratings from Neon
  const ratings = await getCurrentRatings(game.season);

  const overallRanks = new Map<string, number>();
  [...ratings]
    .sort((a, b) => b.overallRating - a.overallRating)
    .forEach((r, idx) => overallRanks.set(r.team, idx + 1));

  const offenseRanks = new Map<string, number>();
  [...ratings]
    .sort((a, b) => b.offenseRating - a.offenseRating)
    .forEach((r, idx) => offenseRanks.set(r.team, idx + 1));

  const defenseRanks = new Map<string, number>();
  [...ratings]
    .sort((a, b) => b.defenseRating - a.defenseRating)
    .forEach((r, idx) => defenseRanks.set(r.team, idx + 1));

  const awayRatingRow = ratings.find((r) => r.team === game.awayTeam);
  const homeRatingRow = ratings.find((r) => r.team === game.homeTeam);

  const awayRating: TeamRatingSummary = {
    team: game.awayTeam,
    rank: overallRanks.get(game.awayTeam) ?? null,
    overallRating: awayRatingRow?.overallRating ?? 0,
    offenseRating: awayRatingRow?.offenseRating ?? 0,
    offenseRank: offenseRanks.get(game.awayTeam) ?? null,
    defenseRating: awayRatingRow?.defenseRating ?? 0,
    defenseRank: defenseRanks.get(game.awayTeam) ?? null,
  };

  const homeRating: TeamRatingSummary = {
    team: game.homeTeam,
    rank: overallRanks.get(game.homeTeam) ?? null,
    overallRating: homeRatingRow?.overallRating ?? 0,
    offenseRating: homeRatingRow?.offenseRating ?? 0,
    offenseRank: offenseRanks.get(game.homeTeam) ?? null,
    defenseRating: homeRatingRow?.defenseRating ?? 0,
    defenseRank: defenseRanks.get(game.homeTeam) ?? null,
  };

  const marketView = marketSpreadView(game.homeTeam, game.awayTeam, game.homeTeamSpreadLine);
  const modelView = modelSpreadView(game.homeTeam, game.awayTeam, game.predictedSpread);

  return {
    gameId: game.gameId,
    season: game.season,
    week: game.week,
    startDate: game.startDate,
    homeTeam: game.homeTeam,
    awayTeam: game.awayTeam,
    systemName: displaySystemName(game.systemName) ?? "Blitzkrieg V5",
    modelId: game.modelId,
    publicationMode: game.modelId ? "predictions" : "market",
    marketSpread: spreadLabel(marketView),
    modelSpread: spreadLabel(modelView),
    marketTotal: game.totalLine,
    modelTotal: game.predictedTotal,
    spreadLean: game.spreadLean as "home" | "away" | null,
    totalLean: game.totalLean as "over" | "under" | null,
    edgeSpread: game.edgeSpread,
    edgeTotal: game.edgeTotal,
    highConfidence: Boolean(game.highConfidence),
    homeFinalPoints,
    awayFinalPoints,
    awayRating,
    homeRating,
  };
});
