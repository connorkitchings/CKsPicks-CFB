import { sql, type SQL } from "drizzle-orm";
import { rowsOf, existsFrom } from "./db-result.ts";
import { CHART_SETS, CHART_SET_KEYS, CHART_SET_PROJECTIONS, RELEASE_PROJECTIONS, type ChartSet } from "./season-release-query.ts";

/** Release identity is pinned for the whole request, including fallback before cutover. */
export type ReleaseEnvironment = "preview" | "production";
export type SeasonReleaseContext = {
  releaseId: string;
  environment: ReleaseEnvironment;
  season: number;
  activeWeek: number;
  activatedAt: Date;
  /** The chart projection set the release recorded, when all its relations exist; else null. */
  chartSet: ChartSet | null;
};

export const chartsAvailable = (chartSet: ChartSet | null) => chartSet !== null;
export const explosivenessAvailable = (chartSet: ChartSet | null) => chartSet === "charts_v2";

export function releaseEnvironment(env: Record<string, string | undefined>): ReleaseEnvironment {
  const explicit = env.CFB_ARTIFACT_ENV;
  if (explicit && explicit !== "preview" && explicit !== "production") {
    throw new Error("CFB_ARTIFACT_ENV must identify preview or production");
  }
  if (explicit === "preview" || explicit === "production") return explicit;
  return (env.VERCEL_ENV === "preview" ? "preview" : "production");
}

/** Create once per request; resolved promises retain the pointer across activation. */
export function createReleaseContextResolver(
  load: (season: number, environment: ReleaseEnvironment) => Promise<SeasonReleaseContext | null>,
) {
  const contexts = new Map<string, Promise<SeasonReleaseContext | null>>();
  return (season: number, environment: ReleaseEnvironment) => {
    if (!Number.isInteger(season) || season < 2021 || season > 2100) {
      throw new Error("Invalid release season");
    }
    const key = `${environment}:${season}`;
    if (!contexts.has(key)) contexts.set(key, load(season, environment));
    return contexts.get(key)!;
  };
}

const relationsColumn = (set: ChartSet) => `${set}_relations`;

/** The set whose keys exactly equal the recorded keys and whose relations all exist. */
function chartSetOf(row: Record<string, unknown>): ChartSet | null {
  const recorded = Array.isArray(row.projection_keys) ? row.projection_keys.map(String).sort() : [];
  return CHART_SETS.find((set) => row[relationsColumn(set)] === true
    && recorded.length === CHART_SET_KEYS[set].length
    && recorded.every((key, index) => key === CHART_SET_KEYS[set][index])) ?? null;
}

export async function loadReleaseContext(
  execute: (query: SQL) => Promise<unknown>,
  season: number, environment: ReleaseEnvironment,
): Promise<SeasonReleaseContext | null> {
  const exists = await execute(sql`SELECT to_regclass('public.season_releases') IS NOT NULL AS exists`);
  if (!existsFrom(exists)) return null;
  const rows = rowsOf(await execute(sql`
    SELECT release_id, environment, season, active_week, activated_at,
      ARRAY(SELECT jsonb_object_keys(projection_checks) ORDER BY 1) AS projection_keys,
      ${sql.join(CHART_SETS.map((set) => sql`(SELECT bool_and(to_regclass('public.' || name) IS NOT NULL)
         FROM unnest(${sql.param(CHART_SET_PROJECTIONS[set])}::text[]) AS names(name)) AS ${sql.identifier(relationsColumn(set))}`), sql`, `)}
    FROM season_releases WHERE environment = ${environment} AND season = ${season} AND status = 'active'
  `));
  if (rows.length === 0) return null;
  if (rows.length !== 1) throw new Error("Multiple active season releases");
  const row = rows[0];
  const missing = rowsOf(await execute(sql`
    SELECT name FROM unnest(${sql.param(RELEASE_PROJECTIONS)}::text[]) AS names(name)
    WHERE to_regclass('public.' || name) IS NULL
  `));
  if (missing.length) throw new Error("Active season release has missing serving projections");
  const activatedAt = new Date(String(row.activated_at));
  if (row.environment !== environment || row.season !== season) throw new Error("Release environment or season mismatch");
  if (!row.release_id || Number.isNaN(activatedAt.getTime()) || !Number.isInteger(row.active_week)) {
    throw new Error("Invalid active season release");
  }
  return {
    releaseId: String(row.release_id), environment, season, activeWeek: Number(row.active_week), activatedAt,
    chartSet: chartSetOf(row),
  };
}
