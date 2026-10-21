/**
 * Cross-request data cache keyed by the active season release.
 *
 * `releaseCached(name, load, options)` wraps a loader in Next's `unstable_cache`. The key is
 * the deployment ID, release environment, `releaseId`, `chartSet`, loader name and arguments,
 * the entry is tagged `release:<releaseId>`, and it never expires unless `options.revalidate`
 * says so. Entries with `revalidate` also carry a time bucket (`floor(now / revalidate)`) as
 * the last key part. `unstable_cache` revalidation is stale-while-revalidate (the first
 * request after expiry is served the old value), so it cannot bound staleness by itself.
 * A new bucket is a different key, hence a cache miss computed synchronously, and entries of
 * older buckets are never read again. GUARANTEE: a change to mutable state is visible within
 * the TTL; the first request after the TTL blocks on one query. If that query throws, the
 * request fails like an uncached one (no stale fallback). The tag is constant across buckets,
 * so `revalidateTag` / `release:<id>` expiry reaches every bucket's entry. It is bypassed (the loader runs directly) when `CFB_UI_TEST_MODE=1`, when
 * `CFB_DATA_CACHE=0` (kill switch), and when the request has no release (legacy tables).
 *
 * IMMUTABILITY FINDINGS (checked against src/cks_picks_cfb/season/release.py and the legacy
 * scripts/pipeline/{score_to_db,freeze_week,publish_to_db}.py):
 *
 * - Every `season_release_*` projection (games, game_results, predictions, prediction_grades,
 *   market_*, system_stats, v5_rating_snapshots, team_*, site_week_selections, matchup
 *   publications, team_resume) is insert-only, keyed by `release_id`; staging a colliding
 *   release raises "immutable release collision". The legacy scripts write the live tables
 *   (games, game_results, system_stats, prediction_grades, ...), which a release never reads
 *   because the release CTEs shadow them. Loaders reading only these tables are immutable
 *   per release id: cached with no expiry.
 * - The one live table a release reads is `public.prediction_runs`, filtered to the release's
 *   selected run ids (season-release-query.ts). Release staging treats `state`, `scored_at`,
 *   `frozen_at`, `published_at` (and `created_at`) as outside the immutable set, and the
 *   legacy scripts mutate them: freeze_week.py sets `state='frozen'`, `frozen_at` and may set
 *   `evidence_class='missed'`; score_to_db.py sets `state='scored'`, `scored_at`. So a loader
 *   that reads `state` or `evidence_class` can change after activation. Those entries carry
 *   `revalidate: 3600` (one hour cap, enforced with a key time bucket) rather than the run
 *   state in the key, so a legacy freeze or score becomes visible within an hour, or
 *   immediately via `release:<id>` tag.
 *
 * Per loader:
 *   queries.ts   getCurrentWeek (release branch) ........ immutable (site_week_selections)
 *                getSeasonCompletedGames ................ immutable (games, game_results)
 *                getMarketSelectionsForRuns ............. immutable (selections, quotes)
 *                getTeamSeasonStats / PossessionStats ... immutable (release stat tables)
 *                getRunForWeek, getAvailableWeeks, getScoredWeeks, getUpcomingWeeks,
 *                getGamesForWeek, getMarketGamesForWeek, getSystemStatsThroughWeek,
 *                getBiggestEdgesRecord .................. mutable (prediction_runs state /
 *                                                         evidence_class): revalidate 3600
 *   v5.ts        getSelectedRatingSource and everything built on it (getCurrentRatings,
 *                getRatingPeriods, getWeeklyRatings, getTeamHistory), getTeamGames
 *                (callers pass names resolved by resolveTeam, which bounds the keys),
 *                getV5PerformanceSplit, getV5PerformanceDetail
 *                                                      .. mutable (evidence_class): 3600
 *                team résumé reads (season_release_team_resume) ... immutable
 *   chart-queries.ts  every chart loader ................. immutable (release chart tables)
 *   matchup.ts   game identity, rating-manifest and stat-provenance lookups ... immutable
 *                (the slate it builds on is cached by queries.ts with its own cap)
 * - `getHistoricalModelContext` reads a live table and is deliberately not cached.
 */
import { publicationScope } from "./publication.ts";
import type { SeasonReleaseContext } from "./season-release-context.ts";

/** Entries above this serialized size are logged: Vercel limits one cache entry to about 2 MB. */
export const CACHE_WARN_BYTES = 1_500_000;

/** Cap for entries that read `prediction_runs` state or evidence class (see the findings above). */
export const RUN_STATE_REVALIDATE_SECONDS = 3600;
export const RUN_STATE_CACHE = { revalidate: RUN_STATE_REVALIDATE_SECONDS } as const;

const TAG = "$cks";

/** JSON codec that preserves `Date` and `Map`, which plain JSON would flatten to strings/objects. */
export function encodeCacheValue(value: unknown): string {
  return JSON.stringify(value, function (this: Record<string, unknown>, key: string, plain: unknown) {
    const original = this[key];
    if (original instanceof Date) {
      return { [TAG]: "date", v: Number.isNaN(original.getTime()) ? null : original.toISOString() };
    }
    if (original instanceof Map) return { [TAG]: "map", v: [...original.entries()] };
    return plain;
  });
}

export function decodeCacheValue<T>(text: string): T {
  return JSON.parse(text, (_key, value) => {
    if (value && typeof value === "object" && TAG in value) {
      const tagged = value as { [TAG]: string; v: unknown };
      if (tagged[TAG] === "date") return new Date(tagged.v === null ? NaN : (tagged.v as string));
      if (tagged[TAG] === "map") return new Map(tagged.v as Array<[unknown, unknown]>);
    }
    return value;
  }) as T;
}

type Env = Record<string, string | undefined>;

export const deploymentId = (env: Env) => env.VERCEL_DEPLOYMENT_ID ?? env.NEXT_DEPLOYMENT_ID ?? "local";

/** True when the cache must not be used at all (test fixtures, kill switch). */
export const cacheDisabled = (env: Env) => env.CFB_UI_TEST_MODE === "1" || env.CFB_DATA_CACHE === "0";

/** The `unstable_cache` key parts: loader, deployment, environment, release, chart set, arguments. */
export function releaseCacheKey(
  name: string, env: Env, context: Pick<SeasonReleaseContext, "environment" | "releaseId" | "chartSet">, args: readonly unknown[],
  bucket?: number,
): string[] {
  const parts = [name, deploymentId(env), context.environment, context.releaseId, context.chartSet ?? "none", JSON.stringify(args)];
  return bucket === undefined ? parts : [...parts, `bucket:${bucket}`];
}

/** Index of the `ttlSeconds`-wide window containing `nowMs`; a new window means a new cache key. */
export const timeBucket = (nowMs: number, ttlSeconds: number) => Math.floor(nowMs / (ttlSeconds * 1000));

/**
 * Key parts for the active-release pointer lookup. Blocking refresh after `ttlSeconds` by the
 * same bucket mechanism as `releaseCacheKey`.
 */
export function pointerCacheKey(
  tag: string, env: Env, environment: string, season: number, nowMs: number, ttlSeconds: number,
): string[] {
  return [tag, deploymentId(env), environment, String(season), `bucket:${timeBucket(nowMs, ttlSeconds)}`];
}

export const releaseTag = (releaseId: string) => `release:${releaseId}`;

export type CacheOptions<A extends unknown[]> = {
  /** Seconds before the entry is refreshed; omit for no expiry (immutable release data). */
  revalidate?: number;
  /** Season whose release scopes the entry; defaults to a numeric first argument, else the published season. */
  season?: (args: A) => number;
};

type TextLoader = (...args: unknown[]) => Promise<string>;

export type CacheDeps = {
  env: () => Env;
  /** Epoch milliseconds; injectable so tests control the time bucket. */
  now: () => number;
  getContext: (season: number) => Promise<SeasonReleaseContext | null>;
  cache: (load: TextLoader, keyParts: string[], options: { tags: string[]; revalidate: number | false }) => Promise<TextLoader>;
  warn: (message: string) => void;
};

export function createReleaseCached(deps: CacheDeps) {
  return function releaseCached<A extends unknown[], T>(
    name: string,
    load: (...args: A) => Promise<T>,
    options: CacheOptions<A> = {},
  ): (...args: A) => Promise<T> {
    return async (...args: A) => {
      const env = deps.env();
      if (cacheDisabled(env)) return load(...args);
      const season = options.season ? options.season(args) : typeof args[0] === "number" ? args[0] : publicationScope.season;
      const context = await deps.getContext(season);
      if (!context) return load(...args);
      const cached = await deps.cache(
        async (...inner: unknown[]) => {
          const text = encodeCacheValue(await load(...(inner as A)));
          if (text.length > CACHE_WARN_BYTES) deps.warn(`release cache entry ${name} is ${text.length} bytes`);
          return text;
        },
        releaseCacheKey(name, env, context, args, options.revalidate === undefined ? undefined : timeBucket(deps.now(), options.revalidate)),
        { tags: [releaseTag(context.releaseId)], revalidate: options.revalidate ?? false },
      );
      return decodeCacheValue<T>(await cached(...args));
    };
  };
}

/** Production wiring. Next and the release resolver load lazily so the pure parts stay unit-testable. */
export const releaseCached = createReleaseCached({
  env: () => process.env,
  now: () => Date.now(),
  getContext: async (season) => (await import("./season-release")).getSeasonReleaseContext(season),
  cache: async (load, keyParts, options) => (await import("next/cache")).unstable_cache(load, keyParts, options),
  warn: (message) => console.warn(message),
});
