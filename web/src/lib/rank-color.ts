/*
 * One color scale for every team rank (1 = best of `total`, default 138): green (best),
 * through an amber midpoint, to red (worst). The same rule holds for every ranked column, so a
 * lower rank number is always greener (SOS rank 1 = hardest schedule = green). Hues live in
 * globals.css (.rank-chip).
 *
 * The scale is nonlinear so the extremes read as clearly green / red: the outer
 * RANK_SATURATION share of ranks on each side is solid (rank <= ~32 and >= ~108 of 138),
 * and the middle ranks ease between them with a smoothstep through the amber midpoint.
 */
export const RANK_TOTAL = 138;

/** Share of the rank range, at each end, that sits on the solid green / red plateau. */
export const RANK_SATURATION = 0.225;

/**
 * Position on the scale: 0 = best (solid green), 0.5 = amber midpoint, 1 = worst (solid red);
 * null for an invalid rank. Non-decreasing in `rank` and odd-symmetric around 0.5.
 */
export function rankColorMix(rank: number | null | undefined, total: number = RANK_TOTAL): number | null {
  if (typeof rank !== "number" || !Number.isFinite(rank) || rank < 1) return null;
  if (!Number.isFinite(total) || total <= 1) return 0;
  const linear = Math.min(1, Math.max(0, (rank - 1) / (total - 1)));
  // m in [-1, 1] across the easing band; smoothstep(x) with x = (1 + m) / 2 is 0.5 + m(3 - m^2) / 4.
  const m = Math.min(1, Math.max(-1, (linear - 0.5) / (0.5 - RANK_SATURATION)));
  return 0.5 + (m * (3 - m * m)) / 4;
}
