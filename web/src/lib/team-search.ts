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

/** Search canonical schools and known aliases; return canonical names only. */
export function searchTeams(query: string, limit = 8): string[] {
  const wanted = normalized(query);
  if (!wanted) return [];
  return DIRECTORY.filter(({ terms }) => terms.some((term) => term.includes(wanted)))
    .sort((a, b) => Number(b.terms.includes(wanted)) - Number(a.terms.includes(wanted)))
    .slice(0, limit).map(({ team }) => team);
}
