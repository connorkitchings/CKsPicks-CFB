/** Pure helpers for the /matchup index (a game picker for the matchup pages). */

export interface IndexGame {
  gameId: number;
  startDate: Date;
  homeTeam: string;
  awayTeam: string;
}

export interface DayGroup<T extends IndexGame> {
  /** e.g. "Saturday, Oct 3" in the given time zone. */
  label: string;
  games: T[];
}

/** Games grouped by local calendar day, days and games in kickoff order. */
export function groupGamesByDay<T extends IndexGame>(
  games: readonly T[],
  timeZone = "America/New_York",
): DayGroup<T>[] {
  const dayKey = new Intl.DateTimeFormat("en-CA", { timeZone });
  const label = new Intl.DateTimeFormat("en-US", {
    timeZone,
    weekday: "long",
    month: "short",
    day: "numeric",
  });
  const sorted = [...games].sort(
    (a, b) => a.startDate.getTime() - b.startDate.getTime() || a.gameId - b.gameId,
  );
  const groups = new Map<string, DayGroup<T>>();
  for (const game of sorted) {
    const key = dayKey.format(game.startDate);
    const group = groups.get(key) ?? { label: label.format(game.startDate), games: [] };
    group.games.push(game);
    groups.set(key, group);
  }
  return [...groups.values()];
}

/** The requested week when it is available, else the fallback (e.g. the current week). */
export function pickWeek(
  requested: string | undefined,
  available: readonly number[],
  fallback: number | null,
): number | null {
  const parsed = requested === undefined ? NaN : Number(requested);
  if (Number.isInteger(parsed) && available.includes(parsed)) return parsed;
  if (fallback !== null && available.includes(fallback)) return fallback;
  return available.length ? Math.max(...available) : null;
}
