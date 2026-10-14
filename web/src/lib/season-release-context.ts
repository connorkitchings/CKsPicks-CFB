import { sql, type SQL } from "drizzle-orm";
import { rowsOf, existsFrom } from "./db-result.ts";
import { RELEASE_PROJECTIONS } from "./season-release-query.ts";

/** Release identity is pinned for the whole request, including fallback before cutover. */
export type ReleaseEnvironment = "preview" | "production";
export type SeasonReleaseContext = {
  releaseId: string;
  environment: ReleaseEnvironment;
  season: number;
  activeWeek: number;
  activatedAt: Date;
};

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

export async function loadReleaseContext(
  execute: (query: SQL) => Promise<unknown>,
  season: number, environment: ReleaseEnvironment,
): Promise<SeasonReleaseContext | null> {
  const exists = await execute(sql`SELECT to_regclass('public.season_releases') IS NOT NULL AS exists`);
  if (!existsFrom(exists)) return null;
  const rows = rowsOf(await execute(sql`
    SELECT release_id, environment, season, active_week, activated_at
    FROM season_releases WHERE environment = ${environment} AND season = ${season} AND status = 'active'
  `));
  if (rows.length === 0) return null;
  if (rows.length !== 1) throw new Error("Multiple active season releases");
  const row = rows[0];
  const missing = rowsOf(await execute(sql`
    SELECT name FROM unnest(${RELEASE_PROJECTIONS}::text[]) AS names(name)
    WHERE to_regclass('public.' || name) IS NULL
  `));
  if (missing.length) throw new Error("Active season release has missing serving projections");
  const activatedAt = new Date(String(row.activated_at));
  if (row.environment !== environment || row.season !== season) throw new Error("Release environment or season mismatch");
  if (!row.release_id || Number.isNaN(activatedAt.getTime()) || !Number.isInteger(row.active_week)) {
    throw new Error("Invalid active season release");
  }
  return { releaseId: String(row.release_id), environment, season, activeWeek: Number(row.active_week), activatedAt };
}
