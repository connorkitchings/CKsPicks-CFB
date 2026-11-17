/**
 * The paired model-versus-line errors behind the Model page scatter and its table.
 *
 * Pure (no database imports). Eligibility is exactly `comparableGames` in `performance-market.ts`:
 * the retained pre-kickoff line, a final score, a forecast and a graded target, pushes included.
 */
import { comparableGames, type ComparedGame, type MarketGame, type MarketTarget } from "./performance-market.ts";

/** Minimal serializable client model: one eligible game. Errors are prediction minus actual. */
export type PairedError = ComparedGame;

export type CloserSide = "model" | "market" | "even";
export type PairedSortKey = "game" | "week" | "forecast" | "line" | "actual" | "modelError" | "lineError" | "closer";
export type SortDirection = "asc" | "desc";

export const DEFAULT_TARGET: MarketTarget = "spread";

/** Normalizes a raw `?target=` value; anything unknown (or repeated) falls back to the spread. */
export function parseTarget(value: string | string[] | null | undefined): MarketTarget {
  return value === "total" ? "total" : DEFAULT_TARGET;
}

/** The eligible paired errors for one target. */
export function pairedErrors(games: readonly MarketGame[], target: MarketTarget): PairedError[] {
  return comparableGames(games, target);
}

export const modelAbsError = (pair: PairedError): number => Math.abs(pair.modelError);
export const lineAbsError = (pair: PairedError): number => Math.abs(pair.lineError);

/**
 * Which side is strictly closer to the final score. On the scatter (market absolute error on x,
 * model absolute error on y) "model" is below the equal-error diagonal, "market" above it.
 */
export function closerSide(pair: PairedError): CloserSide {
  const model = modelAbsError(pair);
  const line = lineAbsError(pair);
  if (model < line) return "model";
  if (line < model) return "market";
  return "even";
}

/** Upper bound shared by both axes so the diagonal is a true 45 degree line; at least 1. */
export function scatterDomain(pairs: readonly PairedError[]): number {
  const largest = pairs.reduce((max, pair) => Math.max(max, modelAbsError(pair), lineAbsError(pair)), 0);
  const step = largest > 40 ? 10 : largest > 10 ? 5 : 1;
  return Math.max(step, Math.ceil(largest / step) * step);
}

const CLOSER_RANK: Record<CloserSide, number> = { model: 0, even: 1, market: 2 };

function sortValue(pair: PairedError, key: PairedSortKey): number | string {
  switch (key) {
    case "game": return `${pair.awayTeam} at ${pair.homeTeam}`;
    case "week": return pair.week;
    case "forecast": return pair.model;
    case "line": return pair.line;
    case "actual": return pair.actual;
    case "modelError": return modelAbsError(pair);
    case "lineError": return lineAbsError(pair);
    case "closer": return CLOSER_RANK[closerSide(pair)];
  }
}

/** A sorted copy; ties break on game id ascending so the order is stable in both directions. */
export function sortPairedErrors(
  pairs: readonly PairedError[],
  key: PairedSortKey,
  direction: SortDirection,
): PairedError[] {
  const sign = direction === "asc" ? 1 : -1;
  return [...pairs].sort((a, b) => {
    const left = sortValue(a, key);
    const right = sortValue(b, key);
    const order = typeof left === "string" ? left.localeCompare(right as string) : (left as number) - (right as number);
    return order !== 0 ? sign * order : a.gameId - b.gameId;
  });
}
