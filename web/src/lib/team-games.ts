import { homeSpreadFromMargin, homeSpreadText, marketSpreadView, spreadLabel } from "./betting-format.ts";
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
  const forecast = forecastText(game);
  return forecast === null ? null : `Forecast: ${forecast}`;
}

/** The model's line and total: "Rice -3.5 · 54.8". Null when no forecast exists. */
export function forecastText(game: TeamGameFields): string | null {
  if (game.predictedMargin === null) return null;
  const spread = homeSpreadText(phoneTeamName(game.homeTeam), homeSpreadFromMargin(game.predictedMargin));
  return `${spread}${game.predictedTotal === null ? "" : ` · ${game.predictedTotal.toFixed(1)}`}`;
}

/** A game's market lines. Both are null until a provider posts them. */
export interface TeamGameLines {
  homeTeamSpreadLine: number | null;
  totalLine: number | null;
}

/** The market line and total: "Rice -3.5 · 51.5", each part left out when missing; null with neither. */
export function marketText(game: TeamGameFields & TeamGameLines): string | null {
  const view = marketSpreadView(game.homeTeam, game.awayTeam, game.homeTeamSpreadLine);
  const parts = [view === null ? null : spreadLabel(view, phoneTeamName), game.totalLine === null ? null : game.totalLine.toFixed(1)];
  const text = parts.filter((part) => part !== null).join(" · ");
  return text === "" ? null : text;
}

export type BetResult = "W" | "L" | "P";
export type OverUnder = "Over" | "Under" | "Push";

/** `team`'s points and the opponent's, or null while the game is not final. */
function sidePoints(game: TeamGameFields, team: string): [number, number] | null {
  if (game.homePoints === null || game.awayPoints === null) return null;
  return game.homeTeam === team ? [game.homePoints, game.awayPoints] : [game.awayPoints, game.homePoints];
}

/** The market spread from `team`'s side: negative when `team` is favored. Null without a line. */
export function lineForTeam(game: TeamGameFields & TeamGameLines, team: string): number | null {
  if (game.homeTeamSpreadLine === null) return null;
  return game.homeTeam === team ? game.homeTeamSpreadLine : -game.homeTeamSpreadLine;
}

/** Against the spread for `team`: null when the game is not final or has no line. */
export function atsResult(game: TeamGameFields & TeamGameLines, team: string): BetResult | null {
  const points = sidePoints(game, team);
  const line = lineForTeam(game, team);
  if (points === null || line === null) return null;
  const covered = points[0] - points[1] + line;
  return covered > 0 ? "W" : covered < 0 ? "L" : "P";
}

/** Total points against the posted total: null when the game is not final or has no total. */
export function overUnderResult(game: TeamGameFields & TeamGameLines): OverUnder | null {
  if (game.homePoints === null || game.awayPoints === null || game.totalLine === null) return null;
  const total = game.homePoints + game.awayPoints;
  return total > game.totalLine ? "Over" : total < game.totalLine ? "Under" : "Push";
}

/** Whether the model's margin picked `team`'s side to win. Null without a final score or a decisive forecast. */
export function modelPickedWinner(game: TeamGameFields, team: string): boolean | null {
  const points = sidePoints(game, team);
  if (points === null || game.predictedMargin === null) return null;
  const actual = points[0] - points[1];
  const predicted = game.homeTeam === team ? game.predictedMargin : -game.predictedMargin;
  if (actual === 0 || predicted === 0) return null;
  return actual > 0 === predicted > 0;
}

/** ATS, over/under and model-winner records over the games where each result exists. */
export interface TeamRecords {
  ats: { wins: number; losses: number; pushes: number };
  overUnder: { overs: number; unders: number; pushes: number };
  modelWinner: { right: number; wrong: number };
}

export function teamRecords(games: readonly (TeamGameFields & TeamGameLines)[], team: string): TeamRecords {
  const records: TeamRecords = {
    ats: { wins: 0, losses: 0, pushes: 0 },
    overUnder: { overs: 0, unders: 0, pushes: 0 },
    modelWinner: { right: 0, wrong: 0 },
  };
  for (const game of games) {
    const ats = atsResult(game, team);
    if (ats === "W") records.ats.wins++;
    else if (ats === "L") records.ats.losses++;
    else if (ats === "P") records.ats.pushes++;
    const ou = overUnderResult(game);
    if (ou === "Over") records.overUnder.overs++;
    else if (ou === "Under") records.overUnder.unders++;
    else if (ou === "Push") records.overUnder.pushes++;
    const picked = modelPickedWinner(game, team);
    if (picked === true) records.modelWinner.right++;
    else if (picked === false) records.modelWinner.wrong++;
  }
  return records;
}

/** "2–3" or "2–3–1" with pushes; the shared wording of the record line. */
export const recordText = (wins: number, losses: number, pushes = 0) => `${wins}–${losses}${pushes > 0 ? `–${pushes}` : ""}`;
