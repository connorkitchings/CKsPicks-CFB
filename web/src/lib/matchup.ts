import { cache } from "react";
import { eq } from "drizzle-orm";
import { db, schema } from "./db.ts";
import { getCurrentRatings } from "./v5.ts";
import {
  displaySystemName,
  isAllowedSeason,
  isPublishedWeek,
  publicationScope,
} from "./publication.ts";
import { getGamesForWeek, getMarketGamesForWeek } from "./queries.ts";
import { selectMatchupView } from "./matchup-visibility.ts";
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
  overallRating: number | null;
  offenseRating: number | null;
  offenseRank: number | null;
  defenseRating: number | null;
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
 * Never produces synthetic or mocked statistical metrics. Model fields follow
 * the same publication boundary as the Picks page: only the explicitly selected
 * public run for a published week, and only in "predictions" mode.
 */
export const getMatchupData = cache(async (gameId: number): Promise<MatchupData | null> => {
  const identity = await db
    .select({ season: schema.games.season, week: schema.games.week })
    .from(schema.games)
    .where(eq(schema.games.gameId, gameId))
    .limit(1);
  if (identity.length === 0) return null;
  const { season, week } = identity[0];

  // Unpublished seasons/weeks do not exist as far as the public site is concerned.
  if (!isAllowedSeason(season) || !isPublishedWeek(season, week)) return null;

  const mode = publicationScope.mode;
  const games =
    mode === "predictions"
      ? await getGamesForWeek(season, week)
      : await getMarketGamesForWeek(season, week);
  const game = games.find((g) => g.gameId === gameId);
  const view = selectMatchupView(game, mode);
  if (!game || !view) return null;

  const homeFinalPoints = view.homePoints;
  const awayFinalPoints = view.awayPoints;

  // Real ratings from Neon
  const ratings = await getCurrentRatings(season);

  const rankBy = (key: "overallRating" | "offenseRating" | "defenseRating") => {
    const ranks = new Map<string, number>();
    [...ratings]
      .sort((a, b) => b[key] - a[key])
      .forEach((r, idx) => ranks.set(r.team, idx + 1));
    return ranks;
  };
  const overallRanks = rankBy("overallRating");
  const offenseRanks = rankBy("offenseRating");
  const defenseRanks = rankBy("defenseRating");

  const summarize = (team: string): TeamRatingSummary => {
    const row = ratings.find((r) => r.team === team);
    return {
      team,
      rank: overallRanks.get(team) ?? null,
      overallRating: row?.overallRating ?? null,
      offenseRating: row?.offenseRating ?? null,
      offenseRank: offenseRanks.get(team) ?? null,
      defenseRating: row?.defenseRating ?? null,
      defenseRank: defenseRanks.get(team) ?? null,
    };
  };

  const marketView = marketSpreadView(game.homeTeam, game.awayTeam, view.marketSpreadLine);
  const modelView = modelSpreadView(game.homeTeam, game.awayTeam, view.predictedSpread);

  return {
    gameId: game.gameId,
    season: game.season,
    week: game.week,
    startDate: game.startDate,
    homeTeam: game.homeTeam,
    awayTeam: game.awayTeam,
    systemName: displaySystemName(view.systemName) ?? "Blitzkrieg V5",
    modelId: view.modelId,
    publicationMode: view.publicationMode,
    marketSpread: spreadLabel(marketView),
    modelSpread: spreadLabel(modelView),
    marketTotal: view.marketTotal,
    modelTotal: view.predictedTotal,
    spreadLean: view.spreadLean,
    totalLean: view.totalLean,
    edgeSpread: view.edgeSpread,
    edgeTotal: view.edgeTotal,
    highConfidence: view.highConfidence,
    homeFinalPoints,
    awayFinalPoints,
    awayRating: summarize(game.awayTeam),
    homeRating: summarize(game.homeTeam),
  };
});
