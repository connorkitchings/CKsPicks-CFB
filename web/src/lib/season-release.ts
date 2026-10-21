import { cache } from "react";
import { db } from "./db";
import { publicationScope } from "./publication.ts";
import { releaseEnvironment, createReleaseContextResolver, loadReleaseContext, type SeasonReleaseContext, type ReleaseEnvironment } from "./season-release-context.ts";
import { seasonReleaseDb, type ChartSet } from "./season-release-query.ts";
import { cacheDisabled, decodeCacheValue, encodeCacheValue, pointerCacheKey } from "./release-cache.ts";

/**
 * Seconds an activation may take to show up without a signed `/api/revalidate`. The key
 * carries a time bucket of this width (see `pointerCacheKey`), so the first request after
 * the window blocks on one pointer query instead of being served the old release; if that
 * query throws, the request fails like an uncached one. The tag is constant, so
 * `revalidateTag(RELEASE_POINTER_TAG)` expires every bucket's entry immediately.
 */
export const RELEASE_POINTER_REVALIDATE_SECONDS = 60;
export const RELEASE_POINTER_TAG = "release-pointer";

const readPointer = (season: number, environment: ReleaseEnvironment) =>
  loadReleaseContext((query) => db.execute(query), season, environment);

/** Cross-request active-release lookup; the per-request resolver below still pins one release. */
async function readPointerCached(season: number, environment: ReleaseEnvironment): Promise<SeasonReleaseContext | null> {
  if (cacheDisabled(process.env)) return readPointer(season, environment);
  const { unstable_cache } = await import("next/cache");
  const cached = unstable_cache(
    async () => encodeCacheValue(await readPointer(season, environment)),
    pointerCacheKey(RELEASE_POINTER_TAG, process.env, environment, season, Date.now(), RELEASE_POINTER_REVALIDATE_SECONDS),
    { tags: [RELEASE_POINTER_TAG], revalidate: RELEASE_POINTER_REVALIDATE_SECONDS },
  );
  return decodeCacheValue<SeasonReleaseContext | null>(await cached());
}

const requestResolver = cache(() => createReleaseContextResolver(readPointerCached));

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

const chartsDbForRelease = cache((releaseId: string, chartSet: ChartSet, season: number, environment: ReleaseEnvironment) => {
  void season; void environment;
  return seasonReleaseDb(db, releaseId, { chartSet });
});
/**
 * Release-scoped database with exactly the release's chart relations, plus the chart set
 * that governs which of them exist, both from the request's single memoized context.
 * `null` when there is no active release or it has no recognized chart set. Chart queries
 * never fall back to live tables.
 */
export async function getChartsDb(season = publicationScope.season) {
  const environment = releaseEnvironment(process.env);
  const context = await getSeasonReleaseContext(season, environment);
  if (!context?.chartSet) return null;
  return { db: chartsDbForRelease(context.releaseId, context.chartSet, season, environment), chartSet: context.chartSet };
}
