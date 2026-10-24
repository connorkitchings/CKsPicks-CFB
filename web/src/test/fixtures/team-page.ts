import type { RatingSnapshotRow, TeamGameRow } from "@/lib/charts";
import type { Rating } from "@/lib/rating-periods";
import type { getTeamGames } from "@/lib/v5";
import { v5RatingFixture } from "./publication";

/**
 * Texas, the one fixture team with a full team page: a 4-0 start with lines, graded results and
 * two games ahead (Week 4 at Ohio State is next). Spreads, totals and results are chosen so every
 * ATS, over/under and model-pick outcome appears: ATS 2-1-1, O/U 1-3, model right 3-1.
 */
type FixtureGame = Awaited<ReturnType<typeof getTeamGames>>[number];

const kickoff = (week: number) => new Date(v5RatingFixture.cutoffUtc.getTime() + week * 7 * 864e5);

const game = (gameId: number, week: number, homeTeam: string, awayTeam: string, rest: Omit<FixtureGame, "gameId" | "week" | "startDate" | "homeTeam" | "awayTeam" | "evidenceClass">): FixtureGame =>
  ({ gameId, week, startDate: kickoff(week), homeTeam, awayTeam, evidenceClass: "replay", ...rest });

export const texasGamesFixture: FixtureGame[] = [
  game(1, 0, "Texas", "Ohio State", { homeTeamSpreadLine: -2.5, totalLine: 51.5, predictedMargin: 3.5, predictedTotal: 52, homePoints: 24, awayPoints: 21 }),
  game(3, 1, "Georgia", "Texas", { homeTeamSpreadLine: 6.5, totalLine: 49.5, predictedMargin: -4, predictedTotal: 50.1, homePoints: 21, awayPoints: 24 }),
  game(4, 2, "Texas", "Alabama", { homeTeamSpreadLine: -7, totalLine: 55, predictedMargin: 7, predictedTotal: 53.3, homePoints: 35, awayPoints: 17 }),
  game(5, 3, "LSU", "Texas", { homeTeamSpreadLine: 3, totalLine: 56.5, predictedMargin: 1, predictedTotal: 57.2, homePoints: 27, awayPoints: 30 }),
  game(2, 4, "Ohio State", "Texas", { homeTeamSpreadLine: -7, totalLine: 55.5, predictedMargin: 6.2, predictedTotal: 54.84, homePoints: null, awayPoints: null }),
  game(6, 5, "Texas", "Rice", { homeTeamSpreadLine: -10.5, totalLine: 48, predictedMargin: 9.8, predictedTotal: 50.2, homePoints: null, awayPoints: null }),
];

/** Texas's four charted team-games, matching the played rows of `texasGamesFixture`. */
export const texasGameStatsFixture: TeamGameRow[] = texasGamesFixture.filter((g) => g.homePoints !== null).map((g, i): TeamGameRow => {
  const home = g.homeTeam === "Texas";
  const plays = 62 + i * 3;
  return {
    week: g.week, gameId: g.gameId, team: "Texas", opponent: home ? g.awayTeam : g.homeTeam, site: home ? "home" : "away",
    pointsFor: (home ? g.homePoints : g.awayPoints)!, pointsAgainst: (home ? g.awayPoints : g.homePoints)!,
    offPlays: plays, offSuccessN: plays, offSuccessSum: Math.round(plays * (0.4 + i * 0.03)), offEpaN: plays, offEpaSum: 1.5 + i,
    defPlays: plays + 4, defSuccessN: plays + 4, defSuccessSum: Math.round((plays + 4) * (0.45 - i * 0.04)), defEpaN: plays + 4, defEpaSum: 2 - i,
  };
});

/** Overall ratings for weeks 0-4 of every fixture team; Texas climbs from second to first. */
export function teamRankSnapshotsFixture(current: readonly Rating[]): RatingSnapshotRow[] {
  const drift = new Map([["Texas", 0.6], ["Ohio State", -0.1]]);
  return [0, 1, 2, 3, 4].flatMap((week) => current.map((row): RatingSnapshotRow => ({
    week, team: row.team,
    offenseRating: row.offenseRating, offenseVariance: row.offenseVariance,
    defenseRating: row.defenseRating, defenseVariance: row.defenseVariance,
    overallRating: row.overallRating + (week - 4) * (drift.get(row.team) ?? 0.05), overallVariance: row.overallVariance,
  })));
}
