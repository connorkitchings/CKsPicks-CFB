import type { TeamGameRow } from "./charts.ts";

/** One played game of the team page's game log: points and per-game success rates for each unit. */
export interface GameLogBar {
  gameId: number;
  week: number;
  opponent: string;
  pointsFor: number;
  pointsAgainst: number;
  /** Offense success rate; null when the game has no counted plays. */
  offenseSuccess: number | null;
  /** Success rate the defense allowed; null when the game has no counted plays. */
  defenseSuccess: number | null;
}

const rate = (sum: number, n: number) => (n > 0 ? sum / n : null);

/**
 * The team's team-game rows by week, with success rates derived per game. `names` lists the
 * spellings the team may carry (a CFBD game name and its stored rating name); rows of any other
 * team are ignored.
 */
export function gameLogBars(rows: readonly TeamGameRow[], names: readonly string[]): GameLogBar[] {
  return rows
    .filter((row) => names.includes(row.team))
    .sort((a, b) => a.week - b.week || a.gameId - b.gameId)
    .map((row) => ({
      gameId: row.gameId,
      week: row.week,
      opponent: row.opponent,
      pointsFor: row.pointsFor,
      pointsAgainst: row.pointsAgainst,
      offenseSuccess: rate(row.offSuccessSum, row.offSuccessN),
      defenseSuccess: rate(row.defSuccessSum, row.defSuccessN),
    }));
}
