import { homeSpreadFromMargin, homeSpreadText } from "./betting-format.ts";
import { phoneTeamName } from "./team-logos.ts";

export interface TeamGameFields {
  homeTeam: string;
  awayTeam: string;
  predictedMargin: number | null;
  predictedTotal: number | null;
  homePoints: number | null;
  awayPoints: number | null;
}

export const isFinal = (game: TeamGameFields) => game.homePoints !== null && game.awayPoints !== null;

/**
 * What a team page row says about the game, from `team`'s side: "W 59–45" once final, otherwise
 * "Forecast: Rice -3.5 · 54.8", or null when no forecast exists.
 */
export function gameResultText(game: TeamGameFields, team: string): string | null {
  if (game.homePoints !== null && game.awayPoints !== null) {
    const [own, other] = game.homeTeam === team ? [game.homePoints, game.awayPoints] : [game.awayPoints, game.homePoints];
    return `${own === other ? "T" : own > other ? "W" : "L"} ${own}–${other}`;
  }
  if (game.predictedMargin === null) return null;
  const spread = homeSpreadText(phoneTeamName(game.homeTeam), homeSpreadFromMargin(game.predictedMargin));
  return `Forecast: ${spread}${game.predictedTotal === null ? "" : ` · ${game.predictedTotal.toFixed(1)}`}`;
}
