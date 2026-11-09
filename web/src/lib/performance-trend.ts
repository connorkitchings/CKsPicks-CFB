/** Season-to-date record by week and the small-sample band around break-even. Pure. */
import { accuracyRecord, type AccuracyResult } from "./performance-accuracy.ts";

export const BREAK_EVEN_RATE = 0.524;

export type TrendRecord = ReturnType<typeof accuracyRecord>;

export interface TrendGame {
  week: number;
  spreadResult: AccuracyResult;
  totalResult: AccuracyResult;
}

export interface TrendWeek {
  week: number;
  weekly: { spread: TrendRecord; total: TrendRecord; combined: TrendRecord };
  /** Everything from the first week through this one. */
  cumulative: { spread: TrendRecord; total: TrendRecord; combined: TrendRecord };
}

function records(games: readonly TrendGame[]) {
  const spread = games.map((game) => game.spreadResult);
  const total = games.map((game) => game.totalResult);
  return {
    spread: accuracyRecord(spread),
    total: accuracyRecord(total),
    combined: accuracyRecord([...spread, ...total]),
  };
}

/** One row per week in `weeks` (ascending); a week with only pushes has a null rate but still carries the season-to-date record. */
export function weeklyAndCumulative(games: readonly TrendGame[], weeks: readonly number[]): TrendWeek[] {
  return weeks.map((week) => ({
    week,
    weekly: records(games.filter((game) => game.week === week)),
    cumulative: records(games.filter((game) => game.week <= week)),
  }));
}

/** 95% band, in percent, around break-even for `decided` wins plus losses; null with none. */
export function breakEvenBand(decided: number): { low: number; high: number } | null {
  if (!(decided > 0)) return null;
  const half = 1.96 * Math.sqrt((BREAK_EVEN_RATE * (1 - BREAK_EVEN_RATE)) / decided) * 100;
  return { low: BREAK_EVEN_RATE * 100 - half, high: BREAK_EVEN_RATE * 100 + half };
}

/** Plain-language caveat for a win rate; wording only, never a verdict. */
export function breakEvenCaveat(winRate: number | null, decided: number): string | null {
  const band = breakEvenBand(decided);
  if (band === null || winRate === null) return null;
  const low = band.low.toFixed(1);
  const high = band.high.toFixed(1);
  return winRate >= band.low && winRate <= band.high
    ? `Over ${decided} decided picks, a win rate anywhere from ${low}% to ${high}% is within normal luck of break-even.`
    : `Over ${decided} decided picks, normal luck keeps a win rate between ${low}% and ${high}%; this record is outside that range.`;
}
