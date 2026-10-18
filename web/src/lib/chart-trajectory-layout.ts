/** Place endpoint logos on a shared rail without changing the plotted data points. */
export type TrajectoryEndpoint = { team: string; y: number; size: number };

export function layoutTrajectoryEndpoints(
  endpoints: readonly TrajectoryEndpoint[],
  top: number,
  bottom: number,
  gap = 4,
): Map<string, { y: number; size: number }> {
  if (!endpoints.length) return new Map();
  const ordered = [...endpoints].sort((a, b) => a.y - b.y || a.team.localeCompare(b.team));
  // A large group must still fit the available rail. Ordinary conferences retain
  // their full-size logos; scale only when their combined height cannot fit.
  const extent = Math.max(0, bottom - top);
  const actualGap = Math.min(gap, extent / (2 * ordered.length));
  const scale = Math.min(1, Math.max(0, extent - actualGap * (ordered.length - 1)) / ordered.reduce((sum, item) => sum + item.size, 0));
  const placed = ordered.map((item) => ({ ...item, size: item.size * scale }));
  for (let i = 0; i < placed.length; i++) {
    const item = placed[i];
    const previous = placed[i - 1];
    const minimum = previous ? previous.y + previous.size / 2 + actualGap + item.size / 2 : top + item.size / 2;
    item.y = Math.max(item.y, minimum);
  }
  for (let i = placed.length - 1; i >= 0; i--) {
    const item = placed[i];
    const next = placed[i + 1];
    const maximum = next ? next.y - next.size / 2 - actualGap - item.size / 2 : bottom - item.size / 2;
    item.y = Math.min(item.y, maximum);
  }
  return new Map(placed.map(({ team, y, size }) => [team, { y, size }]));
}
