import { LOGO_IDS } from "./team-logos.generated.ts";

export const TEAM_LOGO_MAP: Record<string, string> = {
  "Sam Houston": "Sam Houston State",
  "UL Monroe": "Louisiana Monroe",
  Massachusetts: "UMass",
  "App State": "Appalachian State",
  "San José State": "San Jose State",
  UTSA: "UT San Antonio",
  "Hawai'i": "Hawai_i",
  Hawaii: "Hawai_i",
  "Hawai i": "Hawai_i",
  UConn: "Connecticut",
  "Southern Miss": "Southern Mississippi",
  FIU: "Florida International",
  "Texas A&M": "Texas A&M",
};

/** Link to a team page; the name is a CFBD game name or a stored rating name. */
export function teamHref(name: string): string {
  return `/teams/${encodeURIComponent(name)}`;
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
  // A CFBD name wins ("Florida International" is both a game name and a stored name).
  if (Object.hasOwn(LOGO_IDS, name)) return { gameName: name, ratingName: TEAM_LOGO_MAP[name] ?? name };
  // Otherwise a stored name: the single alias key that is a CFBD name is the game name.
  const gameName = Object.keys(TEAM_LOGO_MAP).find((key) => TEAM_LOGO_MAP[key] === name && Object.hasOwn(LOGO_IDS, key));
  return gameName ? { gameName, ratingName: name } : null;
}
