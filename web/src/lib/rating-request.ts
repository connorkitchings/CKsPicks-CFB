const FIXED_PERIODS = ["current", "preseason", "pre"];
const WEEK_STYLE = /^(?:post-|week-)?\d+$/;

/**
 * Maps a raw `?period=` / `?week=` value to one the ratings loader should see. Anything that is not a
 * fixed tab, one of the release's own period ids, or a retired week-style param becomes `current`, so
 * arbitrary strings never reach `getWeeklyRatings` as uncached queries.
 */
export function normalizeRatingPeriod(requested: string, knownPeriodIds: readonly string[]): string {
  return FIXED_PERIODS.includes(requested) || WEEK_STYLE.test(requested) || knownPeriodIds.includes(requested)
    ? requested
    : "current";
}

/**
 * Whether a period's analysis history can be bounded by the active release. When false the history is only
 * the selected period: preseason, no ratings, or no active release to scope an exact-source read.
 */
export function canBoundHistoryByRelease(input: { period: string; ratingCount: number; hasRelease: boolean }): boolean {
  return input.period !== "preseason" && input.ratingCount > 0 && input.hasRelease;
}
