import { TEAM_LOGO_MAP } from "./teams.ts";

/**
 * v5_rating_snapshots stores nine teams under legacy names ("San Jose State",
 * "Hawai_i", "Appalachian State", ...) while games use CFBD names ("San José
 * State", "Hawai'i", "App State"). TEAM_LOGO_MAP maps the game name to the
 * stored name. These helpers keep lookups by game name working.
 */
export function ratingName(gameTeam: string): string {
  return TEAM_LOGO_MAP[gameTeam] ?? gameTeam;
}

/** Add game-name keys for every ranked legacy name (the original keys stay). */
export function withGameNameAliases<T>(byRatingName: Record<string, T>): Record<string, T> {
  const out = { ...byRatingName };
  for (const [gameName, stored] of Object.entries(TEAM_LOGO_MAP)) {
    if (stored in byRatingName && !(gameName in out)) out[gameName] = byRatingName[stored];
  }
  return out;
}
