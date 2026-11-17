import { LOGO_IDS } from "./team-logos.generated.ts";
import { teamAbbr } from "./team-logos.ts";
import { TEAM_LOGO_MAP } from "./teams.ts";

function normalized(value: string): string {
  return value.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().replace(/[^a-z0-9]/g, "");
}

const DIRECTORY = Object.keys(LOGO_IDS).sort((a, b) => a.localeCompare(b)).map((team) => {
  const ratingName = TEAM_LOGO_MAP[team] ?? team;
  const aliases = Object.keys(TEAM_LOGO_MAP).filter((alias) => TEAM_LOGO_MAP[alias] === ratingName);
  return { team, terms: [team, ratingName, teamAbbr(team), ...aliases].map(normalized) };
});

/** 0 = a name, alias or abbreviation equals the query; 1 = one starts with it; 2 = one contains it; null = no match. */
function matchRank(terms: string[], wanted: string): 0 | 1 | 2 | null {
  if (terms.includes(wanted)) return 0;
  if (terms.some((term) => term.startsWith(wanted))) return 1;
  return terms.some((term) => term.includes(wanted)) ? 2 : null;
}

/**
 * Search canonical schools and known aliases; return canonical names only, exact matches first, then
 * prefix matches, then other substring matches (alphabetical within each group).
 */
export function searchTeams(query: string, limit = 8): string[] {
  const wanted = normalized(query);
  if (!wanted) return [];
  const ranked: { team: string; rank: number }[] = [];
  for (const { team, terms } of DIRECTORY) {
    const rank = matchRank(terms, wanted);
    if (rank !== null) ranked.push({ team, rank });
  }
  // Array.prototype.sort is stable, so the directory's alphabetical order holds within a rank.
  return ranked.sort((a, b) => a.rank - b.rank).slice(0, limit).map(({ team }) => team);
}

/** Text for the persistent live region: the result count, or the no-match message once something is typed. */
export function searchAnnouncement(query: string, count: number): string {
  if (!normalized(query)) return "";
  return count === 0 ? "No matching team" : `${count} ${count === 1 ? "team" : "teams"} found`;
}
