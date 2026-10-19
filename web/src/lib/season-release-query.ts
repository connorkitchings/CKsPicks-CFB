import { getTableColumns, getTableName, sql } from "drizzle-orm";
import type { NeonHttpDatabase } from "drizzle-orm/neon-http";
import * as schema from "./schema.ts";

/** Fixed CTE names shadow legacy relations, including correlated SQL and tie lookups. */
export const CORE_RELEASE_TABLES = [
  "games", "gameVenues", "gameResults", "predictions", "predictionGrades",
  "marketQuotes", "marketSnapshots", "marketSnapshotQuotes", "predictionMarketSelections",
  "systemStats", "v5RatingSnapshots", "teamSeasonStats", "matchupDataPublications",
  "teamGameMeasurements", "teamPossessionStats", "teamPossessionAdjusted",
  "teamRatingComponents", "siteWeekSelections",
] as const;

const CHARTS_V1_TABLES = ["teamSeasonRoster", "teamGameStats", "teamAdjustedEpa"] as const;
/**
 * Team-chart projection sets, frozen per version: a release serves exactly the set it
 * recorded at staging, so a `charts_v1` release never references a later table.
 */
export const CHART_TABLE_SETS = {
  charts_v1: CHARTS_V1_TABLES,
  charts_v2: [...CHARTS_V1_TABLES, "teamGameYardage"],
} as const;
export type ChartSet = keyof typeof CHART_TABLE_SETS;
export const CHART_SETS = Object.keys(CHART_TABLE_SETS) as ChartSet[];

type ReleaseTableKey = (typeof CORE_RELEASE_TABLES)[number] | (typeof CHART_TABLE_SETS)[ChartSet][number];
const releaseName = (key: ReleaseTableKey) => getTableName(schema[key]);
const projectionName = (key: ReleaseTableKey) => `season_release_${releaseName(key)}`;
const perSet = <T>(build: (set: ChartSet) => T) =>
  Object.fromEntries(CHART_SETS.map((set) => [set, build(set)])) as Record<ChartSet, T>;

/** Core relations every active release must expose (existing behavior, unchanged). */
export const RELEASE_PROJECTIONS = CORE_RELEASE_TABLES.map(projectionName);
/**
 * Optional release-scoped relation (migration 0028). It is deliberately not in
 * `CORE_RELEASE_TABLES`: it is absent before 0028 and empty for releases staged without it,
 * so its absence must never fail `loadReleaseContext`. It is read directly with a
 * `release_id` filter, not as a CTE, because a CTE over a missing relation fails the query.
 */
export const TEAM_RESUME_PROJECTION = getTableName(schema.seasonReleaseTeamResume);
/** The `projection_checks` key a release records for the optional résumé table (bare table name). */
const TEAM_RESUME_KEY = "team_resume";
/** The sorted table names a release of each chart set records in `projection_checks`. */
export const CHART_SET_KEYS = perSet((set) => [...CORE_RELEASE_TABLES, ...CHART_TABLE_SETS[set]].map(releaseName).sort());
/** The chart relations each chart set reads. */
export const CHART_SET_PROJECTIONS = perSet((set) => CHART_TABLE_SETS[set].map(projectionName));
export const CHARTS_V1_KEYS = CHART_SET_KEYS.charts_v1;
/**
 * Every projection set a release can record, mirroring `PROJECTION_SETS` in
 * `projection_common.py`, each with the chart set it serves. `resume_v1` is `charts_v2`
 * plus the résumé table, which is read on its own, so it serves `charts_v2`.
 */
export const RECORDED_PROJECTION_SETS: Record<string, { chartSet: ChartSet; keys: readonly string[] }> = {
  charts_v1: { chartSet: "charts_v1", keys: CHART_SET_KEYS.charts_v1 },
  charts_v2: { chartSet: "charts_v2", keys: CHART_SET_KEYS.charts_v2 },
  resume_v1: { chartSet: "charts_v2", keys: [...CHART_SET_KEYS.charts_v2, TEAM_RESUME_KEY].sort() },
};

/** Chart CTEs are added only for `chartSet`'s tables; never fall back to live tables. */
export function seasonReleaseDb(
  db: NeonHttpDatabase<typeof schema>,
  releaseId: string | null,
  options: { chartSet?: ChartSet | null } = {},
) {
  if (!releaseId) return db.with();
  const keys: readonly ReleaseTableKey[] = options.chartSet
    ? [...CORE_RELEASE_TABLES, ...CHART_TABLE_SETS[options.chartSet]]
    : CORE_RELEASE_TABLES;
  const relations = keys.map((key) => {
    const table = schema[key];
    const name = getTableName(table);
    // Identifiers come exclusively from the fixed canonical schema, never release input.
    const projection = sql`${sql.identifier(`season_release_${name}`)} AS ${sql.identifier(name)}`;
    const columns = sql.join(Object.values(getTableColumns(table)).map((column) => sql.identifier(column.name)), sql`, `);
    return db.$with(name, getTableColumns(table)).as(sql`SELECT ${columns} FROM ${projection} WHERE release_id = ${releaseId}`);
  });
  // Runs are immutable; membership is pinned by the release's selected weeks.
  const runColumns = sql.join(Object.values(getTableColumns(schema.predictionRuns)).map((column) => sql.identifier(column.name)), sql`, `);
  const runs = db.$with("prediction_runs", getTableColumns(schema.predictionRuns)).as(sql`SELECT ${runColumns} FROM public.prediction_runs
    WHERE run_id IN (SELECT run_id FROM season_release_site_week_selections WHERE release_id = ${releaseId})`);
  return db.with(...relations, runs);
}
