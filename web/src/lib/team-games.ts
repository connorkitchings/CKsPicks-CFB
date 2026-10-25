import { homeSpreadFromMargin, homeSpreadText, marketSpreadView, signedSpread, spreadBetLabel, spreadLabel, totalBetLabel } from "./betting-format.ts";
import { deriveSpreadView, deriveTotalView } from "./publication.ts";
import { phoneTeamName } from "./team-logos.ts";

export interface TeamGameFields {
  homeTeam: string;
  awayTeam: string;
  predictedMargin: number | null;
  predictedTotal: number | null;
  homePoints: number | null;
  awayPoints: number | null;
}

/** True once both scores are recorded. */
export const isFinal = (game: { homePoints: number | null; awayPoints: number | null }) => game.homePoints !== null && game.awayPoints !== null;

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

/** The model's line alone: "Rice -3.5". Null when no forecast exists. */
export function forecastLine(game: TeamGameFields): string | null {
  if (game.predictedMargin === null) return null;
  return homeSpreadText(phoneTeamName(game.homeTeam), homeSpreadFromMargin(game.predictedMargin));
}

/** The model's line and total: "Rice -3.5 · 54.8". Null when no forecast exists. */
export function forecastText(game: TeamGameFields): string | null {
  const line = forecastLine(game);
  return line === null ? null : `${line}${game.predictedTotal === null ? "" : ` · ${game.predictedTotal.toFixed(1)}`}`;
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

/** A line from one side as the schedule prints it: "-3.5", "+7.0", "PK"; "—" without a line. */
export function lineText(line: number | null): string {
  return line === null ? "—" : line === 0 ? "PK" : signedSpread(line);
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

/** ATS and over/under records over the games where each result exists. */
export interface TeamRecords {
  ats: { wins: number; losses: number; pushes: number };
  overUnder: { overs: number; unders: number; pushes: number };
}

export function teamRecords(games: readonly (TeamGameFields & TeamGameLines)[], team: string): TeamRecords {
  const records: TeamRecords = { ats: { wins: 0, losses: 0, pushes: 0 }, overUnder: { overs: 0, unders: 0, pushes: 0 } };
  for (const game of games) {
    const ats = atsResult(game, team);
    if (ats === "W") records.ats.wins++;
    else if (ats === "L") records.ats.losses++;
    else if (ats === "P") records.ats.pushes++;
    const ou = overUnderResult(game);
    if (ou === "Over") records.overUnder.overs++;
    else if (ou === "Under") records.overUnder.unders++;
    else if (ou === "Push") records.overUnder.pushes++;
  }
  return records;
}

/** A model pick against the market: the label as the app prints a lean, and its result once final. */
export interface ModelPick {
  label: string;
  result: BetResult | null;
}

const settle = (margin: number): BetResult => (margin > 0 ? "W" : margin < 0 ? "L" : "P");

/**
 * The model's side against the market spread, using the app's lean rule (`deriveSpreadView`: home
 * when the forecast margin beats the home line, an exact tie goes to the away side; no minimum
 * edge). Null without a forecast or a line. `result` is null until the game is final.
 */
export function modelSpreadPick(game: TeamGameFields & TeamGameLines): ModelPick | null {
  const { lean } = deriveSpreadView(game.predictedMargin, game.homeTeamSpreadLine);
  const label = spreadBetLabel(phoneTeamName(game.homeTeam), phoneTeamName(game.awayTeam), lean, game.homeTeamSpreadLine);
  if (lean === null || label === null || game.homeTeamSpreadLine === null) return null;
  if (game.homePoints === null || game.awayPoints === null) return { label, result: null };
  const homeCover = game.homePoints - game.awayPoints + game.homeTeamSpreadLine;
  return { label, result: settle(lean === "home" ? homeCover : -homeCover) };
}

/** The model's over/under against the market total (an exact tie goes to the under). Null without a forecast total or a line. */
export function modelTotalPick(game: TeamGameFields & TeamGameLines): ModelPick | null {
  const { lean } = deriveTotalView(game.predictedTotal, game.totalLine);
  const label = totalBetLabel(lean, game.totalLine);
  if (lean === null || label === null || game.totalLine === null) return null;
  if (game.homePoints === null || game.awayPoints === null) return { label, result: null };
  const over = game.homePoints + game.awayPoints - game.totalLine;
  return { label, result: settle(lean === "over" ? over : -over) };
}

/** The team the forecast margin has winning, as the schedule prints names. Null without a decisive forecast. */
export function modelWinnerName(game: TeamGameFields): string | null {
  if (game.predictedMargin === null || game.predictedMargin === 0) return null;
  return phoneTeamName(game.predictedMargin > 0 ? game.homeTeam : game.awayTeam);
}

/** The model's graded picks over the played games: spread and total (W/L/P) and straight-up winners. */
export interface ModelRecords {
  ats: { wins: number; losses: number; pushes: number };
  overUnder: { wins: number; losses: number; pushes: number };
  winner: { right: number; wrong: number };
}

export function modelRecords(games: readonly (TeamGameFields & TeamGameLines)[], team: string): ModelRecords {
  const records: ModelRecords = { ats: { wins: 0, losses: 0, pushes: 0 }, overUnder: { wins: 0, losses: 0, pushes: 0 }, winner: { right: 0, wrong: 0 } };
  const tally = (record: ModelRecords["ats"], result: BetResult | null | undefined) => {
    if (result === "W") record.wins++;
    else if (result === "L") record.losses++;
    else if (result === "P") record.pushes++;
  };
  for (const game of games) {
    tally(records.ats, modelSpreadPick(game)?.result);
    tally(records.overUnder, modelTotalPick(game)?.result);
    const picked = modelPickedWinner(game, team);
    if (picked === true) records.winner.right++;
    else if (picked === false) records.winner.wrong++;
  }
  return records;
}

/** Share of decided picks that won, "67%"; pushes are not decisions. Null with none decided. */
export function winPercent(wins: number, losses: number): string | null {
  return wins + losses === 0 ? null : `${Math.round((wins / (wins + losses)) * 100)}%`;
}

/** "2–3" or "2–3–1" with pushes; the shared wording of the record line. */
export const recordText = (wins: number, losses: number, pushes = 0) => `${wins}–${losses}${pushes > 0 ? `–${pushes}` : ""}`;
