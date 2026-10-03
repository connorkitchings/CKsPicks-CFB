/**
 * Matchup pages are a full-time feature of the site (open in production,
 * development, and test mode). Can be emergency-disabled with CFB_MATCHUP_ENABLED=0.
 * The page calls `notFound()` when this is false.
 */
export function isMatchupEnabled(env: Record<string, string | undefined> = process.env): boolean {
  return env.CFB_MATCHUP_ENABLED !== "0";
}
