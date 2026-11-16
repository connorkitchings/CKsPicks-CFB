const FIXED_PERIODS = ["current", "preseason", "pre"];
const WEEK_STYLE = /^(?:post-|week-)?(\d+)$/;

/**
 * Maps a raw `?period=` / `?week=` value to one the ratings loader should see. Anything that is not a
 * fixed tab, one of the release's own period ids, or a retired week-style param naming one of the
 * release's weeks becomes `current`, so arbitrary strings never reach `getWeeklyRatings` as uncached queries.
 */
export function normalizeRatingPeriod(requested: string, knownPeriods: readonly { id: string; postWeek?: number }[]): string {
  const week = WEEK_STYLE.exec(requested)?.[1];
  const known = FIXED_PERIODS.includes(requested)
    || knownPeriods.some((period) => period.id === requested || (week !== undefined && period.postWeek === Number(week)));
  return known ? requested : "current";
}

/**
 * Whether a period's analysis history can be bounded by the active release. When false the history is only
 * the selected period: preseason, no ratings, or no active release to scope an exact-source read.
 */
export function canBoundHistoryByRelease(input: { period: string; ratingCount: number; hasRelease: boolean }): boolean {
  return input.period !== "preseason" && input.ratingCount > 0 && input.hasRelease;
}
