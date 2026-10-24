import { competitionRanks } from "./sos-rank.ts";

export interface TeamRankPoint {
  week: number;
  rating: number;
  rank: number;
}

/**
 * One team's overall rating and its rank among every team's snapshot for each week it has one,
 * ascending by week. Ranks are competition ranks (ties share the lowest rank) among the teams
 * that have a snapshot that week. Weeks without a row for `team` are skipped, not interpolated.
 */
export function teamRankHistory(
  snapshots: readonly { week: number; team: string; overallRating: number }[],
  team: string,
): TeamRankPoint[] {
  const byWeek = new Map<number, { team: string; overallRating: number }[]>();
  for (const row of snapshots) {
    const rows = byWeek.get(row.week);
    if (rows) rows.push(row); else byWeek.set(row.week, [row]);
  }
  const points: TeamRankPoint[] = [];
  for (const week of [...byWeek.keys()].sort((a, b) => a - b)) {
    const rows = byWeek.get(week)!;
    const index = rows.findIndex((row) => row.team === team);
    if (index < 0) continue;
    const rank = competitionRanks(rows.map((row) => row.overallRating))[index];
    if (rank !== null) points.push({ week, rating: rows[index].overallRating, rank });
  }
  return points;
}
