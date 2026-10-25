/**
 * Optional reads (venues, market selections) degrade to "absent" on failure. A cached loader
 * must never store that degraded result, so it reads strictly, throws this instead, and the
 * public wrapper re-runs the loader uncached in tolerant mode.
 */
export class SwallowedReadError extends Error {
  constructor(cause: unknown) {
    super("Optional read failed", { cause });
  }
}

/** How long a degraded (tolerant) result is reused before the strict cached path is retried. */
export const DEGRADED_TTL_MS = 30_000;

type Degraded<T> = { until: number; result: Promise<T> };

/**
 * Runs `cached`; when an optional read inside it fails, runs `tolerant` instead. The degraded
 * result is remembered per argument list for `ttlMs`, so an outage costs one extra loader run
 * per window rather than a strict attempt plus a full uncached rerun on every request.
 */
export function createCachedOrTolerant(ttlMs = DEGRADED_TTL_MS, now: () => number = Date.now) {
  const degraded = new WeakMap<object, Map<string, Degraded<unknown>>>();
  return async function cachedOrTolerant<A extends unknown[], T>(
    cached: (...args: A) => Promise<T>,
    tolerant: (...args: A) => Promise<T>,
    ...args: A
  ): Promise<T> {
    const byArgs = degraded.get(cached) ?? new Map<string, Degraded<unknown>>();
    degraded.set(cached, byArgs);
    const key = JSON.stringify(args);
    const hit = byArgs.get(key);
    if (hit && hit.until > now()) return hit.result as Promise<T>;
    byArgs.delete(key);
    try {
      return await cached(...args);
    } catch (error) {
      if (!(error instanceof SwallowedReadError)) throw error;
      const result = tolerant(...args);
      byArgs.set(key, { until: now() + ttlMs, result });
      result.catch(() => {
        if (byArgs.get(key)?.result === result) byArgs.delete(key);
      });
      return result;
    }
  };
}

export const cachedOrTolerant = createCachedOrTolerant();
