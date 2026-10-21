/*
 * One color scale for every team rank (1 = best of `total`, default 138): a continuous
 * gradient from deep green (rank 1) through neutral (midpoint) to deep red (last).
 * The same rule holds for every ranked column, so a lower rank number is always greener
 * (SOS rank 1 = hardest schedule = green). Hues live in globals.css (.rank-chip).
 */
export const RANK_TOTAL = 138;

/** Position on the scale: 0 = best (green), 0.5 = neutral, 1 = worst (red); null for an invalid rank. */
export function rankColorMix(rank: number | null | undefined, total: number = RANK_TOTAL): number | null {
  if (typeof rank !== "number" || !Number.isFinite(rank) || rank < 1) return null;
  if (!Number.isFinite(total) || total <= 1) return 0;
  return Math.min(1, Math.max(0, (rank - 1) / (total - 1)));
}
