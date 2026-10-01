/**
 * Matchup pages are closed in production until explicitly enabled
 * (CFB_MATCHUP_ENABLED=1). They are open in local development and fixture test mode.
 * The page calls `notFound()` when this is false.
 */
export function isMatchupEnabled(env: Record<string, string | undefined> = process.env): boolean {
  return (
    env.CFB_UI_TEST_MODE === "1" ||
    env.CFB_MATCHUP_ENABLED === "1" ||
    env.NODE_ENV !== "production"
  );
}
