import type { Rating } from "./rating-periods.ts";
import { competitionRanks, rankSosByTeam, type SosRanks } from "./sos-rank.ts";
import type { TeamRankPoint } from "./team-rank-history.ts";

/** One team's current rating row with its ranks against the whole field, and its latest weekly move. */
export interface TeamSummary {
  rating: Rating;
  overallRank: number | null;
  offenseRank: number | null;
  defenseRank: number | null;
  waaRank: number | null;
  sos: SosRanks;
  /** Versus the previous stored week: rank spots gained (positive = moved up) and the rating change. Null before a second week. */
  change: { spots: number; delta: number } | null;
}

/**
 * `ratingName`'s row of `current` ranked against every team of the period (a rank is relative to the
 * whole field, so pass all of them). Null when the team has no row.
 */
export function buildTeamSummary(current: readonly Rating[], ratingName: string, rankHistory: readonly TeamRankPoint[]): TeamSummary | null {
  const index = current.findIndex((row) => row.team === ratingName);
  const rating = current[index];
  if (!rating) return null;
  const rankOf = (pick: (row: Rating) => number | null | undefined) => competitionRanks(current.map(pick))[index];
  const [previous, latest] = rankHistory.slice(-2);
  return {
    rating,
    overallRank: rankOf((row) => row.overallRating),
    offenseRank: rankOf((row) => row.offenseRating),
    defenseRank: rankOf((row) => row.defenseRating),
    waaRank: rankOf((row) => row.waa),
    sos: rankSosByTeam(current).get(ratingName)!,
    change: previous && latest ? { spots: previous.rank - latest.rank, delta: latest.rating - previous.rating } : null,
  };
}
