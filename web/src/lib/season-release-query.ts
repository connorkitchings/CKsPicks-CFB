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

/** Weekly team-chart projections (projection set `charts_v1`); absent from older releases. */
export const CHART_RELEASE_TABLES = ["teamSeasonRoster", "teamGameStats", "teamAdjustedEpa"] as const;

type ReleaseTableKey = (typeof CORE_RELEASE_TABLES)[number] | (typeof CHART_RELEASE_TABLES)[number];
const releaseName = (key: ReleaseTableKey) => getTableName(schema[key]);

/** Core relations every active release must expose (existing behavior, unchanged). */
export const RELEASE_PROJECTIONS = CORE_RELEASE_TABLES.map((key) => `season_release_${releaseName(key)}`);
export const CHART_PROJECTIONS = CHART_RELEASE_TABLES.map((key) => `season_release_${releaseName(key)}`);
/** The table names a `charts_v1` release records in `projection_checks`. */
export const CHARTS_V1_KEYS = [...CORE_RELEASE_TABLES, ...CHART_RELEASE_TABLES].map(releaseName).sort();

/** Chart CTEs are added only when `charts` is true; never fall back to live tables. */
export function seasonReleaseDb(
  db: NeonHttpDatabase<typeof schema>,
  releaseId: string | null,
  options: { charts?: boolean } = {},
) {
  if (!releaseId) return db.with();
  const keys: readonly ReleaseTableKey[] = options.charts
    ? [...CORE_RELEASE_TABLES, ...CHART_RELEASE_TABLES]
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
