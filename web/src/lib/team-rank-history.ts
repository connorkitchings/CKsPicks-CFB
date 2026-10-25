import { niceTicks } from "./charts.ts";
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

const MAX_TICKS = 5;

export interface TrendAxis {
  /** Padded value window; rank 1 sits at the low end. */
  lo: number;
  hi: number;
  /** Round values inside the window; a rating axis that spans zero includes 0. */
  ticks: number[];
}

/**
 * The y window and round tick values for a trend of `values`. The window is padded so a flat or
 * short series keeps height; rank windows start no lower than #1 and ticks are whole ranks.
 */
export function trendAxis(values: readonly number[], measure: "rating" | "rank"): TrendAxis {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = Math.max((max - min) * 0.15, measure === "rank" ? 2 : 0.1);
  const lo = measure === "rank" ? Math.max(1, min - pad) : min - pad;
  const hi = max + pad;
  // niceTicks favours steps of 1 and 2; ask for fewer ticks until at most five fit the small plot.
  let ticks = niceTicks(lo, hi, 4);
  for (let count = 3; ticks.length > MAX_TICKS && count >= 1; count--) ticks = niceTicks(lo, hi, count);
  return { lo, hi, ticks: measure === "rank" ? ticks.filter(Number.isInteger) : ticks };
}

/**
 * Weeks to label on the x axis: always the first and last, plus round intermediate weeks that
 * exist in `weeks` and sit at least `minGap` (in the same unit as `width`) from their neighbours.
 */
export function trendWeekLabels(weeks: readonly number[], width: number, minGap: number): number[] {
  const first = weeks[0];
  const last = weeks[weeks.length - 1];
  if (weeks.length < 3 || last === first) return [...new Set([first, last])];
  const at = (week: number) => ((week - first) / (last - first)) * width;
  const kept = [first];
  for (const week of niceTicks(first, last, Math.max(1, Math.floor(width / minGap)))) {
    if (week > first && week < last && weeks.includes(week) && at(week) - at(kept[kept.length - 1]) >= minGap && at(last) - at(week) >= minGap) kept.push(week);
  }
  return [...kept, last];
}
