import { and, asc, eq } from "drizzle-orm";
import { cache } from "react";
import { schema } from "./db";
import { guardRows, type RowSpec } from "./row-guard.ts";
import { getChartsDb } from "./season-release";
import { explosivenessAvailable } from "./season-release-context.ts";
import type { AdjustedRow, RosterRow, TeamGameRow, TeamGameYardageRow } from "./charts.ts";


// ---------------------------------------------------------------------------
// Team charts (release projections `team_season_roster`, `team_game_stats`,
// `team_adjusted_epa` and, for `charts_v2`, `team_game_yardage`). Every query runs on
// the request-pinned, release-scoped database with the release's chart relations; with
// no active release, or one staged without them, the result is `null` and the live
// tables are never read. Errors propagate so the page can show an unavailable state.
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
export const getTeamSeasonRoster = cache(async (season: number): Promise<RosterRow[] | null> => {
  const charts = await getChartsDb(season);
  if (!charts) return null;
  const t = schema.teamSeasonRoster;
  const rows = await charts.db.select({ team: t.team, conference: t.conference }).from(t)
    .where(eq(t.season, season)).orderBy(asc(t.team));
  return guardRows("team_season_roster", rows, ROSTER_SPEC);
});

/** Every team-game row of the release (about 1.5k rows by season end). */
export const getTeamGameStats = cache(async (season: number): Promise<TeamGameRow[] | null> => {
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
});

/** Yardage counts per team-game, or null unless the release serves `charts_v2`. */
export const getTeamGameYardage = cache(async (season: number): Promise<TeamGameYardageRow[] | null> => {
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
});

/** `as_of_week` windows stored in the release, ascending. */
export const getTeamAdjustedWeeks = cache(async (season: number): Promise<number[] | null> => {
  const charts = await getChartsDb(season);
  if (!charts) return null;
  const t = schema.teamAdjustedEpa;
  const rows = await charts.db.selectDistinct({ asOfWeek: t.asOfWeek }).from(t)
    .where(eq(t.season, season)).orderBy(asc(t.asOfWeek));
  return rows.map((row) => row.asOfWeek);
});

/** Adjusted EPA/play rows of one stored window. */
export const getTeamAdjustedEpa = cache(async (season: number, asOfWeek: number): Promise<AdjustedRow[] | null> => {
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
});

/** Adjusted EPA/play rows of every stored window (about 2k rows by Week 8). */
export const getTeamAdjustedEpaAll = cache(async (season: number): Promise<AdjustedRow[] | null> => {
  const charts = await getChartsDb(season);
  if (!charts) return null;
  const t = schema.teamAdjustedEpa;
  const rows = await charts.db.select({
    asOfWeek: t.asOfWeek, team: t.team, role: t.role,
    rawEpaPerPlay: t.rawEpaPerPlay, venueCorrection: t.venueCorrection,
    opponentAdjustment: t.opponentAdjustment, adjustedEpaPerPlay: t.adjustedEpaPerPlay,
    epaN: t.epaN, games: t.games, adjustedRank: t.adjustedRank, cohortSize: t.cohortSize,
  }).from(t).where(eq(t.season, season)).orderBy(asc(t.asOfWeek), asc(t.team), asc(t.role));
  guardRows("team_adjusted_epa", rows, ADJUSTED_SPEC);
  return rows as AdjustedRow[];
});
