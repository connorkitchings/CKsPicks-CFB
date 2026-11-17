/**
 * Label for a stats snapshot taken `asOfWeek` (the snapshot covers games before that week's slate).
 * Weeks 0 and 1 have no completed week behind them, so "through Week -1" would read as an error.
 */
export function statsWindowLabel(asOfWeek: number): string {
  if (asOfWeek <= 0) return "Preseason statistics";
  if (asOfWeek === 1) return "Statistics before Week 1";
  return `Statistics through Week ${asOfWeek - 1}`;
}
