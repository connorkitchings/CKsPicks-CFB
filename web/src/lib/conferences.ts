import { TEAM_LOGO_MAP } from "./teams.ts";

/** Conference helpers shared by the slate, ratings and chart pages; kept apart from the chart math so non-chart routes do not bundle it. */

export type RosterRow = { team: string; conference: string | null };

/** Power Four conferences; Notre Dame is included by name (it has no conference). */
export const P4_CONFERENCES = ["ACC", "Big Ten", "Big 12", "SEC"] as const;
export const P4_INDEPENDENTS = ["Notre Dame"] as const;

/** "all", "p4" (Power Four plus Notre Dame) or a conference name from the roster. */
export type ConferenceFilter = string;

export function isP4(team: string, conference: string | null): boolean {
  return (
    (conference !== null && (P4_CONFERENCES as readonly string[]).includes(conference)) ||
    (P4_INDEPENDENTS as readonly string[]).includes(team)
  );
}

export function matchesConference(filter: ConferenceFilter, team: string, conference: string | null): boolean {
  if (filter === "all") return true;
  if (filter === "p4") return isP4(team, conference);
  return conference === filter;
}

/** Conferences present in the published roster, ascending. */
export function conferenceOptions(roster: readonly RosterRow[]): string[] {
  return [...new Set(roster.flatMap((r) => (r.conference ? [r.conference] : [])))].sort();
}

/**
 * Map both CFBD and legacy rating/game team names to their published conference.
 */
export function buildConferenceMap(roster: readonly RosterRow[]): Map<string, string | null> {
  const map = new Map<string, string | null>();
  for (const { team, conference } of roster) {
    map.set(team, conference);
  }
  for (const [gameName, stored] of Object.entries(TEAM_LOGO_MAP)) {
    if (map.has(gameName) && !map.has(stored)) {
      map.set(stored, map.get(gameName) ?? null);
    } else if (map.has(stored) && !map.has(gameName)) {
      map.set(gameName, map.get(stored) ?? null);
    }
  }
  return map;
}

export function matchesTeamConference(
  filter: ConferenceFilter,
  team: string,
  conferenceMap: ReadonlyMap<string, string | null>,
): boolean {
  return matchesConference(filter, team, conferenceMap.get(team) ?? null);
}
