import { LOGO_IDS } from "./team-logos.generated.ts";
import { TEAM_LOGO_MAP } from "./teams.ts";

/** Link to a team page; the name is a CFBD game name or a stored rating name. Spaces become underscores. */
export function teamHref(name: string): string {
  return `/teams/${encodeURIComponent(name.replaceAll(" ", "_"))}`;
}

export type ResolvedTeam = { gameName: string; ratingName: string };

/**
 * Resolve a /teams/[team] segment to the CFBD name used by games and the name
 * stored in rating snapshots. Accepts either spelling ("San José State" or
 * "San Jose State"); returns null for names that are not known schools.
 */
export function resolveTeam(segment: string): ResolvedTeam | null {
  let name = segment;
  if (name.includes("%")) {
    try { name = decodeURIComponent(name); } catch { return null; }
  }
  // Links write spaces as underscores; the exact segment is tried first so "%20" links and names that
  // really contain an underscore keep working.
  return lookupTeam(name) ?? (name.includes("_") ? lookupTeam(name.replaceAll("_", " ")) : null);
}

function lookupTeam(name: string): ResolvedTeam | null {
  // A CFBD name wins ("Florida International" is both a game name and a stored name).
  if (Object.hasOwn(LOGO_IDS, name)) return { gameName: name, ratingName: TEAM_LOGO_MAP[name] ?? name };
  // Otherwise a stored name: the single alias key that is a CFBD name is the game name.
  const gameName = Object.keys(TEAM_LOGO_MAP).find((key) => TEAM_LOGO_MAP[key] === name && Object.hasOwn(LOGO_IDS, key));
  return gameName ? { gameName, ratingName: name } : null;
}
