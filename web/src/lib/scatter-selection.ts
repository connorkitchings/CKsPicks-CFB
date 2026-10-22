/** Screen coordinates deliberately avoid assumptions about SVG scale or scroll position. */
export type ScreenPoint = { team: string; x: number; y: number };

export function nearestScatterTeams(points: readonly ScreenPoint[], x: number, y: number): string[] {
  const nearby = points
    .map((point) => ({ team: point.team, distance: Math.hypot(point.x - x, point.y - y) }))
    .filter((point) => point.distance <= 24)
    .sort((a, b) => a.distance - b.distance || (a.team < b.team ? -1 : a.team > b.team ? 1 : 0));
  if (!nearby.length) return [];
  return nearby.filter((point) => point.distance - nearby[0].distance <= 8).slice(0, 3).map((point) => point.team);
}
