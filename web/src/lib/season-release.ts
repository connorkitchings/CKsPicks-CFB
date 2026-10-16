import { cache } from "react";
import { db } from "./db";
import { publicationScope } from "./publication.ts";
import { releaseEnvironment, createReleaseContextResolver, loadReleaseContext, type SeasonReleaseContext, type ReleaseEnvironment } from "./season-release-context.ts";
import { seasonReleaseDb } from "./season-release-query.ts";

const requestResolver = cache(() => createReleaseContextResolver((season, environment) =>
  loadReleaseContext((query) => db.execute(query), season, environment),
));

export function getSeasonReleaseContext(
  season = publicationScope.season,
  environment: ReleaseEnvironment = releaseEnvironment(process.env),
): Promise<SeasonReleaseContext | null> {
  if (process.env.CFB_UI_TEST_MODE === "1") return Promise.resolve(null);
  return requestResolver()(season, environment);
}

// Query cache keys carry the resolved identity, rather than only a season number.
const dbForRelease = cache((releaseId: string | null, season: number, environment: ReleaseEnvironment) => {
  void season; void environment;
  return seasonReleaseDb(db, releaseId);
});
export async function getSeasonDb(season = publicationScope.season) {
  const environment = releaseEnvironment(process.env);
  const context = await getSeasonReleaseContext(season, environment);
  return dbForRelease(context?.releaseId ?? null, season, environment);
}

const chartsDbForRelease = cache((releaseId: string, season: number, environment: ReleaseEnvironment) => {
  void season; void environment;
  return seasonReleaseDb(db, releaseId, { charts: true });
});
/**
 * Release-scoped database that includes the chart relations, or `null` when there is no
 * active release or it was not staged with the chart projections. Chart queries never
 * fall back to live tables.
 */
export async function getChartsDb(season = publicationScope.season) {
  const environment = releaseEnvironment(process.env);
  const context = await getSeasonReleaseContext(season, environment);
  if (!context?.chartsAvailable) return null;
  return chartsDbForRelease(context.releaseId, season, environment);
}
