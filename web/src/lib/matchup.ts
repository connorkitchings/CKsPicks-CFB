import { cache } from "react";
import { and, desc, eq, inArray, lte } from "drizzle-orm";
import { db, schema } from "./db.ts";
import { getRatingsAsOf } from "./v5.ts";
import { ratingName } from "./rating-names.ts";
import {
  displaySystemName,
  isAllowedSeason,
  isPublishedWeek,
  publicationScope,
} from "./publication.ts";
import {
  getGamesForWeek,
  getMarketGamesForWeek,
  getTeamPossessionStats,
  getTeamSeasonStats,
} from "./queries.ts";
import {
  buildMatchupStats,
  type MatchupStats,
} from "./team-stats.ts";
import { selectMatchupView } from "./matchup-visibility.ts";
import { matchupLineage, type MatchupLineageStatus } from "./matchup-lineage.ts";
import { RowContractError } from "./row-guard.ts";
import {
  marketSpreadView,
  modelSpreadView,
  spreadEdge,
  spreadLabel,
  totalEdge,
} from "./betting-format.ts";

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
  /** When this game's forecast row was last updated (not the kickoff time). */
  updatedAt: Date;
  homeTeam: string;
  awayTeam: string;
  /** Season W-L as of kickoff (null before a team's first game). */
  homeRecord: string | null;
  awayRecord: string | null;
  venueCity: string | null;
  venueState: string | null;
  neutralSite: boolean | null;
  /** Null in market mode: no model is published, so no system is named. */
  systemName: string | null;
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
  /** Model minus market, as the Picks cards show it (null in market mode). */
  modelSpreadEdge: number | null;
  modelTotalEdge: number | null;
  /** Sportsbook behind each best line when the run recorded one. */
  spreadSource: string | null;
  totalSource: string | null;
  highConfidence: boolean;
  // Final results if game completed
  homeFinalPoints: number | null;
  awayFinalPoints: number | null;
  // Ratings
  awayRating: TeamRatingSummary;
  homeRating: TeamRatingSummary;
  /** Pre-game team stats; null when no snapshot is published for this week. */
  stats: MatchupStats | null;
  /** True when stored stat rows broke their contract; distinct from "not published". */
  statsUnavailable: boolean;
  lineageStatus: MatchupLineageStatus;
  lineageReason: string;
}

/** Silver-based and V5 possession stats for the two teams (raw values only). */
async function getMatchupStatRows(season: number, week: number, teams: string[]) {
  try {
    const [silver, possession] = await Promise.all([
      getTeamSeasonStats(season, week, teams),
      getTeamPossessionStats(season, week, teams),
    ]);
    return { rows: [...silver, ...possession], unavailable: false };
  } catch (error) {
    // Never show partial or coerced stats when the stored rows broke their contract.
    if (error instanceof RowContractError) return { rows: [], unavailable: true };
    throw error;
  }
}

/**
 * Fetch and construct authentic matchup breakdown for a specific gameId.
 * Never produces synthetic or mocked statistical metrics. Model fields follow
 * the same publication boundary as the Picks page: only the explicitly selected
 * public run for a published week, and only in "predictions" mode.
 */
export const getMatchupData = cache(async (gameId: number): Promise<MatchupData | null> => {
  if (process.env.CFB_UI_TEST_MODE === "1") {
    const fx = await import("@/test/fixtures/matchup");
    return fx.fixtureMatchupForId(gameId);
  }
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

  const selectedRunId = game.publicationMode === "predictions" ? game.runId : null;
  const selectedRun = selectedRunId
    ? await db.select({ ratingManifestSha256: schema.predictionRuns.ratingManifestSha256 })
      .from(schema.predictionRuns).where(eq(schema.predictionRuns.runId, selectedRunId)).limit(1)
    : [];
  const forecastRatingManifestSha256 = selectedRun[0]?.ratingManifestSha256 ?? null;

  // Ratings known before kickoff, matching the pre-game stats snapshot (never
  // post-game ratings that already include this result).
  const ratings = await getRatingsAsOf(season, game.startDate.getTime());
  const ratingProvenanceRows = await db.selectDistinct({
    team: schema.v5RatingSnapshots.team,
    sourceManifestSha256: schema.v5RatingSnapshots.sourceManifestSha256,
  }).from(schema.v5RatingSnapshots).where(and(
    eq(schema.v5RatingSnapshots.season, season),
    eq(schema.v5RatingSnapshots.snapshotClass, "current"),
    lte(schema.v5RatingSnapshots.cutoffUtc, game.startDate),
    inArray(schema.v5RatingSnapshots.team, [ratingName(game.homeTeam), ratingName(game.awayTeam)]),
  )).orderBy(desc(schema.v5RatingSnapshots.cutoffUtc));
  const latestRatingManifestByTeam = new Map<string, string>();
  for (const row of ratingProvenanceRows) {
    if (!latestRatingManifestByTeam.has(row.team)) latestRatingManifestByTeam.set(row.team, row.sourceManifestSha256);
  }
  const ratingManifests = new Set(latestRatingManifestByTeam.values());
  const ratingManifestSha256 = latestRatingManifestByTeam.size === 2 && ratingManifests.size === 1
    ? [...ratingManifests][0]
    : null;

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

  // Nine teams are stored in v5_rating_snapshots under legacy names ("San Jose
  // State", "Hawai_i", ...); TEAM_LOGO_MAP maps the game's CFBD name to them.
  const summarize = (team: string): TeamRatingSummary => {
    const key = ratingName(team);
    const row = ratings.find((r) => r.team === key);
    return {
      team,
      rank: overallRanks.get(key) ?? null,
      overallRating: row?.overallRating ?? null,
      offenseRating: row?.offenseRating ?? null,
      offenseRank: offenseRanks.get(key) ?? null,
      defenseRating: row?.defenseRating ?? null,
      defenseRank: defenseRanks.get(key) ?? null,
    };
  };

  const marketView = marketSpreadView(game.homeTeam, game.awayTeam, view.marketSpreadLine);
  const modelView = modelSpreadView(game.homeTeam, game.awayTeam, view.predictedSpread);

  const statRows = await getMatchupStatRows(season, week, [game.homeTeam, game.awayTeam]);
  let statProvenanceRows: {
    team: string;
    ratingManifestSha256: string;
    measurementManifestSha256: string;
  }[] = [];
  let publishedMeasurementManifestSha256: string | null = null;
  let lineageLookupUnavailable = false;
  try {
    statProvenanceRows = await db.selectDistinct({
      team: schema.teamPossessionStats.team,
      ratingManifestSha256: schema.teamPossessionStats.ratingManifestSha256,
      measurementManifestSha256: schema.teamPossessionStats.measurementManifestSha256,
    }).from(schema.teamPossessionStats).where(and(
      eq(schema.teamPossessionStats.season, season),
      eq(schema.teamPossessionStats.asOfWeek, week),
      inArray(schema.teamPossessionStats.team, [game.homeTeam, game.awayTeam]),
    ));
  } catch {
    lineageLookupUnavailable = true;
  }
  const statRatingManifests = new Set(statProvenanceRows.map((row) => row.ratingManifestSha256));
  const statMeasurementManifests = new Set(statProvenanceRows.map((row) => row.measurementManifestSha256));
  const statRatingManifestSha256 = statRatingManifests.size === 1 ? [...statRatingManifests][0] : null;
  const statMeasurementManifestSha256 = statMeasurementManifests.size === 1 ? [...statMeasurementManifests][0] : null;
  if (statRatingManifestSha256 && statMeasurementManifestSha256 && !lineageLookupUnavailable) {
    try {
      const published = await db.select({ measurementManifestSha256: schema.matchupDataPublications.measurementManifestSha256 })
        .from(schema.matchupDataPublications).where(and(
          eq(schema.matchupDataPublications.season, season),
          eq(schema.matchupDataPublications.ratingManifestSha256, statRatingManifestSha256),
          eq(schema.matchupDataPublications.measurementManifestSha256, statMeasurementManifestSha256),
        )).limit(1);
      publishedMeasurementManifestSha256 = published[0]?.measurementManifestSha256 ?? null;
    } catch {
      lineageLookupUnavailable = true;
    }
  }
  const lineage = matchupLineage({
    forecastRunId: view.publicationMode === "predictions" ? selectedRunId : null,
    forecastRatingManifestSha256,
    ratingManifestSha256,
    statRatingManifestSha256,
    statMeasurementManifestSha256,
    publishedMeasurementManifestSha256,
    requiredStatRows: 2,
    presentStatRows: new Set(statProvenanceRows.map((row) => row.team)).size,
    statsUnavailable: statRows.unavailable || lineageLookupUnavailable,
  });

  return {
    gameId: game.gameId,
    season: game.season,
    week: game.week,
    startDate: game.startDate,
    updatedAt: game.updatedAt,
    homeTeam: game.homeTeam,
    awayTeam: game.awayTeam,
    homeRecord: game.homeRecord ?? null,
    awayRecord: game.awayRecord ?? null,
    venueCity: game.venueCity ?? null,
    venueState: game.venueState ?? null,
    neutralSite: game.neutralSite ?? null,
    systemName: displaySystemName(view.systemName),
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
    modelSpreadEdge: spreadEdge(modelView, marketView),
    modelTotalEdge: totalEdge(view.predictedTotal, view.marketTotal),
    spreadSource: view.spreadSource,
    totalSource: view.totalSource,
    highConfidence: view.highConfidence,
    homeFinalPoints,
    awayFinalPoints,
    awayRating: summarize(game.awayTeam),
    homeRating: summarize(game.homeTeam),
    stats: statRows.unavailable
      ? null
      : buildMatchupStats(statRows.rows, week, game.awayTeam, game.homeTeam),
    statsUnavailable: statRows.unavailable,
    lineageStatus: lineage.status,
    lineageReason: lineage.reason,
  };
});
