/** Season-to-date record by week. Pure. */
import { accuracyRecord, type AccuracyResult } from "./performance-accuracy.ts";

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
