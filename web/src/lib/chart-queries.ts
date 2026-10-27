import { and, asc, eq, sql } from "drizzle-orm";
import { cache } from "react";
import { db as legacyDb, schema } from "./db";
import { guardRows, type RowSpec } from "./row-guard.ts";
import { releaseCached } from "./release-cache.ts";
import { getChartsDb, getSeasonReleaseContext } from "./season-release";
import { explosivenessAvailable } from "./season-release-context.ts";
import { TEAM_RESUME_PROJECTION } from "./season-release-query.ts";
import { existsFrom, rowsOf } from "./db-result.ts";
import type {
  AdjustedRow,
  PossessionRow,
  RatingSnapshotRow,
  RosterRow,
  SlateMarketGameRow,
  TeamGameRow,
  TeamGameYardageRow,
  TeamResumeChartRow,
  TeamSeasonStatRow,
} from "./charts.ts";


// ---------------------------------------------------------------------------
// Team charts (release projections `team_season_roster`, `team_game_stats`,
// `team_adjusted_epa` and, for `charts_v2`, `team_game_yardage`; plus the core
// `v5_rating_snapshots` and `team_possession_adjusted` every release carries). Every query runs on
// the request-pinned, release-scoped database with the release's chart relations; with
// no active release, or one staged without them, the result is `null` and the live
// tables are never read. Errors propagate so the page can show an unavailable state.
// Every loader reads release chart tables only, so each is cached per release (release-cache.ts).
// ---------------------------------------------------------------------------

const ROSTER_SPEC: RowSpec = {
  team: { kind: "string" },
  conference: { kind: "string", nullable: true },
};
const GAME_STATS_SPEC: RowSpec = {
  week: { kind: "int" },
  gameId: { kind: "int" },
  team: { kind: "string" },
  opponent: { kind: "string" },
  site: { kind: { enum: ["home", "away", "neutral"] } },
  pointsFor: { kind: "int" },
  pointsAgainst: { kind: "int" },
  offPlays: { kind: "int" },
  offSuccessN: { kind: "int" },
  offSuccessSum: { kind: "number" },
  offEpaN: { kind: "int" },
  offEpaSum: { kind: "number" },
  defPlays: { kind: "int" },
  defSuccessN: { kind: "int" },
  defSuccessSum: { kind: "number" },
  defEpaN: { kind: "int" },
  defEpaSum: { kind: "number" },
};
const YARDAGE_SPEC: RowSpec = {
  gameId: { kind: "int" },
  team: { kind: "string" },
  offYardsN: { kind: "int" },
  offExplosiveN: { kind: "int" },
  offSuccessYardsN: { kind: "int" },
  offSuccessYardsSum: { kind: "number" },
  defYardsN: { kind: "int" },
  defExplosiveN: { kind: "int" },
  defSuccessYardsN: { kind: "int" },
  defSuccessYardsSum: { kind: "number" },
};
const ADJUSTED_SPEC: RowSpec = {
  asOfWeek: { kind: "int" },
  team: { kind: "string" },
  role: { kind: { enum: ["offense", "defense"] } },
  rawEpaPerPlay: { kind: "number" },
  venueCorrection: { kind: "number" },
  opponentAdjustment: { kind: "number" },
  adjustedEpaPerPlay: { kind: "number" },
  epaN: { kind: "int" },
  games: { kind: "int" },
  adjustedRank: { kind: "int" },
  cohortSize: { kind: "int" },
};

/** Published FBS roster (team and conference), or null when charts are not available. */
export const getTeamSeasonRoster = cache(releaseCached("getTeamSeasonRoster", async (season: number): Promise<RosterRow[] | null> => {
  const charts = await getChartsDb(season);
  if (!charts) return null;
  const t = schema.teamSeasonRoster;
  const rows = await charts.db.select({ team: t.team, conference: t.conference }).from(t)
    .where(eq(t.season, season)).orderBy(asc(t.team));
  return guardRows("team_season_roster", rows, ROSTER_SPEC);
}));

/** Every team-game row of the release (about 1.5k rows by season end). */
export const getTeamGameStats = cache(releaseCached("getTeamGameStats", async (season: number): Promise<TeamGameRow[] | null> => {
  const charts = await getChartsDb(season);
  if (!charts) return null;
  const t = schema.teamGameStats;
  const rows = await charts.db.select({
    week: t.week, gameId: t.gameId, team: t.team, opponent: t.opponent, site: t.site,
    pointsFor: t.pointsFor, pointsAgainst: t.pointsAgainst,
    offPlays: t.offPlays, offSuccessN: t.offSuccessN, offSuccessSum: t.offSuccessSum,
    offEpaN: t.offEpaN, offEpaSum: t.offEpaSum,
    defPlays: t.defPlays, defSuccessN: t.defSuccessN, defSuccessSum: t.defSuccessSum,
    defEpaN: t.defEpaN, defEpaSum: t.defEpaSum,
  }).from(t).where(eq(t.season, season)).orderBy(asc(t.week), asc(t.gameId), asc(t.team));
  guardRows("team_game_stats", rows, GAME_STATS_SPEC);
  return rows as TeamGameRow[];
}));

/** Yardage counts per team-game, or null unless the release serves `charts_v2`. */
export const getTeamGameYardage = cache(releaseCached("getTeamGameYardage", async (season: number): Promise<TeamGameYardageRow[] | null> => {
  const charts = await getChartsDb(season);
  if (!charts || !explosivenessAvailable(charts.chartSet)) return null;
  const t = schema.teamGameYardage;
  const rows = await charts.db.select({
    gameId: t.gameId, team: t.team,
    offYardsN: t.offYardsN, offExplosiveN: t.offExplosiveN,
    offSuccessYardsN: t.offSuccessYardsN, offSuccessYardsSum: t.offSuccessYardsSum,
    defYardsN: t.defYardsN, defExplosiveN: t.defExplosiveN,
    defSuccessYardsN: t.defSuccessYardsN, defSuccessYardsSum: t.defSuccessYardsSum,
  }).from(t).where(eq(t.season, season)).orderBy(asc(t.gameId), asc(t.team));
  return guardRows("team_game_yardage", rows, YARDAGE_SPEC);
}));

/** `as_of_week` windows stored in the release, ascending. */
export const getTeamAdjustedWeeks = cache(releaseCached("getTeamAdjustedWeeks", async (season: number): Promise<number[] | null> => {
  const charts = await getChartsDb(season);
  if (!charts) return null;
  const t = schema.teamAdjustedEpa;
  const rows = await charts.db.selectDistinct({ asOfWeek: t.asOfWeek }).from(t)
    .where(eq(t.season, season)).orderBy(asc(t.asOfWeek));
  return rows.map((row) => row.asOfWeek);
}));

/** Adjusted EPA/play rows of one stored window. */
export const getTeamAdjustedEpa = cache(releaseCached("getTeamAdjustedEpa", async (season: number, asOfWeek: number): Promise<AdjustedRow[] | null> => {
  const charts = await getChartsDb(season);
  if (!charts) return null;
  const t = schema.teamAdjustedEpa;
  const rows = await charts.db.select({
    asOfWeek: t.asOfWeek, team: t.team, role: t.role,
    rawEpaPerPlay: t.rawEpaPerPlay, venueCorrection: t.venueCorrection,
    opponentAdjustment: t.opponentAdjustment, adjustedEpaPerPlay: t.adjustedEpaPerPlay,
    epaN: t.epaN, games: t.games, adjustedRank: t.adjustedRank, cohortSize: t.cohortSize,
  }).from(t).where(and(eq(t.season, season), eq(t.asOfWeek, asOfWeek))).orderBy(asc(t.team), asc(t.role));
  guardRows("team_adjusted_epa", rows, ADJUSTED_SPEC);
  return rows as AdjustedRow[];
}));

const RATING_SNAPSHOT_SPEC: RowSpec = {
  week: { kind: "int" },
  team: { kind: "string" },
  offenseRating: { kind: "number" },
  offenseVariance: { kind: "number" },
  defenseRating: { kind: "number" },
  defenseVariance: { kind: "number" },
  overallRating: { kind: "number" },
  overallVariance: { kind: "number" },
};
const nonNegativeVariances = (row: Record<string, unknown>) =>
  ["offenseVariance", "defenseVariance", "overallVariance"].some((key) => (row[key] as number) < 0) ? "negative variance" : null;

/**
 * `current`-class V5 rating snapshots of every roster team for every stored week (the
 * rating after that week's games; about 1.1k rows by Week 7), by week then team.
 */
export const getV5RatingSnapshots = cache(releaseCached("getV5RatingSnapshots", async (season: number): Promise<RatingSnapshotRow[] | null> => {
  const context = await getSeasonReleaseContext(season);
  const charts = await getChartsDb(season);
  if (!charts) return null;
  const r = schema.teamSeasonRoster;

  if (context) {
    const sr = schema.seasonReleaseV5RatingSnapshots;
    const rows = await charts.db.select({
      week: sr.week, team: sr.team,
      offenseRating: sr.offenseRating, offenseVariance: sr.offenseVariance,
      defenseRating: sr.defenseRating, defenseVariance: sr.defenseVariance,
      overallRating: sr.overallRating, overallVariance: sr.overallVariance,
    }).from(sr)
      .innerJoin(r, and(eq(r.season, sr.season), eq(r.team, sr.team)))
      .where(and(eq(sr.releaseId, context.releaseId), eq(sr.season, season), eq(sr.snapshotClass, "current")))
      .orderBy(asc(sr.week), asc(sr.team));
    if (rows.length > 0) {
      return guardRows("season_release_v5_rating_snapshots", rows, RATING_SNAPSHOT_SPEC, [nonNegativeVariances]) as RatingSnapshotRow[];
    }
  }

  const t = schema.v5RatingSnapshots;
  const rows = await charts.db.select({
    week: t.week, team: t.team,
    offenseRating: t.offenseRating, offenseVariance: t.offenseVariance,
    defenseRating: t.defenseRating, defenseVariance: t.defenseVariance,
    overallRating: t.overallRating, overallVariance: t.overallVariance,
  }).from(t)
    .innerJoin(r, and(eq(r.season, t.season), eq(r.team, t.team)))
    .where(and(eq(t.season, season), eq(t.snapshotClass, "current")))
    .orderBy(asc(t.week), asc(t.team));
  return guardRows("v5_rating_snapshots", rows, RATING_SNAPSHOT_SPEC, [nonNegativeVariances]);
}));

const OPTIONAL_NUMBER = { kind: "number", nullable: true } as const;
const OPTIONAL_INT = { kind: "int", nullable: true } as const;
const POSSESSION_SPEC: RowSpec = {
  asOfWeek: { kind: "int" },
  team: { kind: "string" },
  role: { kind: { enum: ["offense", "defense"] } },
  measurementId: { kind: { enum: ["ppp", "epa_per_possession"] } },
  rawValue: OPTIONAL_NUMBER,
  adjustedValue: OPTIONAL_NUMBER,
  opponentAdjustment: OPTIONAL_NUMBER,
  adjustedRank: OPTIONAL_INT,
  cohortSize: OPTIONAL_INT,
  primaryExposure: OPTIONAL_NUMBER,
  games: { kind: "int" },
};

/** `as_of_week` windows of `team_possession_adjusted` stored in the release, ascending. */
export const getTeamPossessionWeeks = cache(releaseCached("getTeamPossessionWeeks", async (season: number): Promise<number[] | null> => {
  const charts = await getChartsDb(season);
  if (!charts) return null;
  const t = schema.teamPossessionAdjusted;
  const rows = await charts.db.selectDistinct({ asOfWeek: t.asOfWeek }).from(t)
    .where(eq(t.season, season)).orderBy(asc(t.asOfWeek));
  return rows.map((row) => row.asOfWeek);
}));

/** Opponent-adjusted possession rows (both roles and measurements) of one stored window. */
export const getTeamPossessionAdjusted = cache(releaseCached("getTeamPossessionAdjusted", async (season: number, asOfWeek: number): Promise<PossessionRow[] | null> => {
  const charts = await getChartsDb(season);
  if (!charts) return null;
  const t = schema.teamPossessionAdjusted;
  const rows = await charts.db.select({
    asOfWeek: t.asOfWeek, team: t.team, role: t.role, measurementId: t.measurementId,
    rawValue: t.rawValue, adjustedValue: t.adjustedValue, opponentAdjustment: t.opponentAdjustment,
    adjustedRank: t.adjustedRank, cohortSize: t.cohortSize, primaryExposure: t.primaryExposure, games: t.games,
  }).from(t).where(and(eq(t.season, season), eq(t.asOfWeek, asOfWeek)))
    .orderBy(asc(t.team), asc(t.role), asc(t.measurementId));
  guardRows("team_possession_adjusted", rows, POSSESSION_SPEC);
  return rows as PossessionRow[];
}));

const SEASON_STAT_SPEC: RowSpec = {
  season: { kind: "int" },
  asOfWeek: { kind: "int" },
  team: { kind: "string" },
  role: { kind: { enum: ["offense", "defense"] } },
  metric: { kind: "string" },
  value: { kind: "number", nullable: true },
  n: { kind: "int" },
  games: { kind: "int" },
  rank: { kind: "int", nullable: true },
  cohortSize: { kind: "int", nullable: true },
};

/** Stored as_of_week windows of team_season_stats in the release, ascending. */
export const getTeamSeasonStatsWeeks = cache(releaseCached("getTeamSeasonStatsWeeks", async (season: number): Promise<number[] | null> => {
  const charts = await getChartsDb(season);
  if (!charts) return null;
  const t = schema.teamSeasonStats;
  const rows = await charts.db.selectDistinct({ asOfWeek: t.asOfWeek }).from(t)
    .where(eq(t.season, season)).orderBy(asc(t.asOfWeek));
  return rows.map((r) => r.asOfWeek);
}));

/** All team season stats for a given week. */
export const getTeamSeasonStatsSnapshot = cache(releaseCached("getTeamSeasonStatsSnapshot", async (season: number, asOfWeek: number): Promise<TeamSeasonStatRow[] | null> => {
  const charts = await getChartsDb(season);
  if (!charts) return null;
  const t = schema.teamSeasonStats;
  const rows = await charts.db.select({
    season: t.season, asOfWeek: t.asOfWeek, team: t.team, role: t.role,
    metric: t.metric, value: t.value, n: t.n, games: t.games,
    rank: t.rank, cohortSize: t.cohortSize,
  }).from(t).where(and(eq(t.season, season), eq(t.asOfWeek, asOfWeek)))
    .orderBy(asc(t.team), asc(t.role), asc(t.metric));
  guardRows("team_season_stats", rows, SEASON_STAT_SPEC);
  return rows as TeamSeasonStatRow[];
}));

const RESUME_CHART_SPEC: RowSpec = {
  periodId: { kind: "string" },
  postWeek: { kind: "int", nullable: true },
  team: { kind: "string" },
  overallRank: { kind: "int" },
  completedGames: { kind: "int" },
  scheduledGames: { kind: "int" },
  wins: { kind: "int" },
  losses: { kind: "int" },
  sor: { kind: "number", nullable: true },
  sorRank: { kind: "int", nullable: true },
  sosPlayedElite: { kind: "number", nullable: true },
};

/** Résumé and strength-of-record rows of the active release, optionally for a specific post-week. */
export const getTeamResume = cache(releaseCached("getTeamResume", async (season: number, postWeek?: number): Promise<TeamResumeChartRow[] | null> => {
  const context = await getSeasonReleaseContext(season);
  if (!context) return null;
  const present = await legacyDb.execute(
    sql`SELECT to_regclass(${`public.${TEAM_RESUME_PROJECTION}`}) IS NOT NULL AS exists`,
  );
  if (!existsFrom(present)) return null;
  const result = await legacyDb.execute(sql`
    SELECT period_id AS "periodId", post_week AS "postWeek", team, overall_rank AS "overallRank",
           completed_games AS "completedGames", scheduled_games AS "scheduledGames",
           wins, losses, sor, sor_rank AS "sorRank", sos_played_elite AS "sosPlayedElite"
    FROM ${sql.identifier(TEAM_RESUME_PROJECTION)}
    WHERE release_id = ${context.releaseId}
    ${postWeek !== undefined ? sql`
      AND post_week = ${postWeek}
      AND period_id = (
        SELECT period_id FROM ${sql.identifier(TEAM_RESUME_PROJECTION)}
        WHERE release_id = ${context.releaseId} AND post_week = ${postWeek}
        ORDER BY cutoff_utc DESC LIMIT 1
      )` : sql`
      AND period_id = (
        SELECT period_id FROM ${sql.identifier(TEAM_RESUME_PROJECTION)}
        WHERE release_id = ${context.releaseId} AND post_week IS NOT NULL
        ORDER BY post_week DESC, cutoff_utc DESC LIMIT 1
      )`}
    ORDER BY overall_rank ASC, team ASC
  `);
  const rows = rowsOf(result);
  return guardRows("season_release_team_resume", rows, RESUME_CHART_SPEC) as TeamResumeChartRow[];
}));

const SLATE_MARKET_SPEC: RowSpec = {
  gameId: { kind: "int" },
  season: { kind: "int" },
  week: { kind: "int" },
  startDate: { kind: "date" },
  homeTeam: { kind: "string" },
  awayTeam: { kind: "string" },
  homeTeamSpreadLine: { kind: "number", nullable: true },
  totalLine: { kind: "number", nullable: true },
  predictedSpread: { kind: "number", nullable: true },
  predictedTotal: { kind: "number", nullable: true },
  edgeSpread: { kind: "number", nullable: true },
  edgeTotal: { kind: "number", nullable: true },
  spreadLean: { kind: { enum: ["home", "away"] }, nullable: true },
  totalLean: { kind: { enum: ["over", "under"] }, nullable: true },
};

/** Weeks containing games in the release. */
export const getSlateMarketWeeks = cache(releaseCached("getSlateMarketWeeks", async (season: number): Promise<number[] | null> => {
  const charts = await getChartsDb(season);
  if (!charts) return null;
  const g = schema.games;
  const rows = await charts.db.selectDistinct({ week: g.week }).from(g)
    .where(eq(g.season, season)).orderBy(asc(g.week));
  return rows.map((r) => r.week);
}));

/** Market line vs model prediction rows for a slate week. */
export const getSlateMarketComparison = cache(releaseCached("getSlateMarketComparison", async (season: number, week: number): Promise<SlateMarketGameRow[] | null> => {
  const charts = await getChartsDb(season);
  if (!charts) return null;
  const g = schema.games;
  const rows = await charts.db.select({
    gameId: g.gameId,
    season: g.season,
    week: g.week,
    startDate: g.startDate,
    homeTeam: g.homeTeam,
    awayTeam: g.awayTeam,
    homeTeamSpreadLine: g.homeTeamSpreadLine,
    totalLine: g.totalLine,
    predictedSpread: g.predictedSpread,
    predictedTotal: g.predictedTotal,
    edgeSpread: g.edgeSpread,
    edgeTotal: g.edgeTotal,
    spreadLean: g.spreadLean,
    totalLean: g.totalLean,
  }).from(g).where(and(eq(g.season, season), eq(g.week, week))).orderBy(asc(g.startDate), asc(g.gameId));
  guardRows("games", rows, SLATE_MARKET_SPEC);
  return rows as SlateMarketGameRow[];
}));
