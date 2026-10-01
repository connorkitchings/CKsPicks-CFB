/**
 * Mathematical calculations and statistical helpers for matchup breakdowns.
 * Kept free of database dependencies for fast, isolated unit testing.
 */

/** Standard normal cumulative distribution function (Abramowitz & Stegun approximation) */
export function normalCdf(z: number): number {
  const t = 1 / (1 + 0.2316419 * Math.abs(z));
  const d = 0.3989422804014327 * Math.exp((-z * z) / 2);
  const prob =
    d *
    t *
    (0.31938153 +
      t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))));
  return z > 0 ? 1 - prob : prob;
}

/**
 * Calculate win probabilities for home and away teams.
 * @param homeMargin Predicted home margin (+home favored, -away favored)
 * @param stdDev Spread standard deviation (defaults to 13.5)
 */
export function calculateWinProbabilities(
  homeMargin: number,
  stdDev = 13.5,
): { homeWinProb: number; awayWinProb: number } {
  const homeProb = normalCdf(homeMargin / (stdDev || 13.5));
  const homeWinProb = Number((homeProb * 100).toFixed(1));
  const awayWinProb = Number((100 - homeWinProb).toFixed(1));
  return { homeWinProb, awayWinProb };
}

/**
 * Calculate projected team point totals from game total and home margin.
 * @param predictedTotal Over/Under projected total points
 * @param homeMargin Predicted home margin (+home favored, -away favored)
 */
export function calculateProjectedPoints(
  predictedTotal: number,
  homeMargin: number,
): { homeProjPoints: number; awayProjPoints: number } {
  const homeProjPoints = Number(((predictedTotal + homeMargin) / 2).toFixed(1));
  const awayProjPoints = Number(((predictedTotal - homeMargin) / 2).toFixed(1));
  return { homeProjPoints, awayProjPoints };
}

/**
 * Get color tier based on national rank (1 to 134):
 *   - Top 25: Elite (indigo/accent)
 *   - 26-60: Above Average (cyan)
 *   - 61-90: Average (neutral/slate)
 *   - 91+: Low (rose/coral)
 */
export function getRankBadgeClass(rank: number): string {
  if (rank <= 25) {
    return "bg-accent/15 text-accent-ink border border-accent/30 font-bold";
  }
  if (rank <= 60) {
    return "bg-cyan-500/10 text-cyan-700 dark:text-cyan-300 border border-cyan-500/20 font-semibold";
  }
  if (rank <= 90) {
    return "bg-surface-inset text-ink-muted border border-line font-medium";
  }
  return "bg-loss-soft text-loss border border-loss/20 font-medium";
}
