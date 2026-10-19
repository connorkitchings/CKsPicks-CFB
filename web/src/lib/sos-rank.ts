/**
 * Pure helpers for the ratings table: schedule-difficulty (SOS) ranks and the sort vocabulary that
 * the server page (URL validation) and the client view share. No React and no database, so
 * `node:test` imports this module directly.
 */

/** Every column the ratings table can order by, in the order the phone sort select lists them. */
export const RATINGS_SORTS = [
  "overall",
  "offense",
  "defense",
  "sor",
  "sos_played",
  "sos_remaining",
  "sos_full",
] as const;
export type RatingsSort = (typeof RATINGS_SORTS)[number];
export type SortDirection = "asc" | "desc";

/** SOS ranks for one team; each is null when that team's average-reference SOS value is null. */
export interface SosRanks {
  played: number | null;
  remaining: number | null;
  full: number | null;
}

/** The average-reference SOS values a team row carries. `Rating` satisfies this structurally. */
export interface SosAverages {
  team: string;
  sosPlayedAverage?: number | null;
  sosRemainingAverage?: number | null;
  sosFullAverage?: number | null;
}

const finiteOrNull = (value: number | null | undefined): number | null => (
  typeof value === "number" && Number.isFinite(value) ? value : null
);

/**
 * Competition ranks, highest value first. Tied values share the lowest rank and the next rank
 * skips, so [70, 60, 60, 50] ranks [1, 2, 2, 4]. Null values rank null and take no place.
 */
export function competitionRanks(values: readonly (number | null | undefined)[]): (number | null)[] {
  const numbers = values.map(finiteOrNull);
  return numbers.map((value) => (
    value === null ? null : 1 + numbers.filter((other) => other !== null && other > value).length
  ));
}

/**
 * SOS ranks for every team of one period, where 1 is the hardest schedule (highest value).
 * Pass every team of the period: a rank is relative to the whole field, so ranking a filtered
 * subset returns different numbers.
 */
export function rankSosByTeam(rows: readonly SosAverages[]): Map<string, SosRanks> {
  const played = competitionRanks(rows.map((row) => row.sosPlayedAverage));
  const remaining = competitionRanks(rows.map((row) => row.sosRemainingAverage));
  const full = competitionRanks(rows.map((row) => row.sosFullAverage));
  return new Map(rows.map((row, i): [string, SosRanks] => [
    row.team,
    { played: played[i] ?? null, remaining: remaining[i] ?? null, full: full[i] ?? null },
  ]));
}

export function isRatingsSort(value: string | undefined): value is RatingsSort {
  return (RATINGS_SORTS as readonly string[]).includes(value ?? "");
}

/** Rating sorts open highest first; rank sorts (SOR and SOS) open at rank 1. */
export function bestFirstDirection(sort: RatingsSort): SortDirection {
  return sort === "sor" || sort.startsWith("sos_") ? "asc" : "desc";
}

/**
 * Resolves raw `?sort=` and `?dir=` values. The retired pre-split `sos` value means SOS Full, and
 * any other unknown sort (including the removed `waa`) falls back to Overall. A missing or unknown
 * direction falls back to the sort's best-first direction.
 */
export function parseRatingsSort(
  sort: string | undefined,
  dir: string | undefined,
): { sort: RatingsSort; dir: SortDirection } {
  const resolved: RatingsSort = sort === "sos" ? "sos_full" : isRatingsSort(sort) ? sort : "overall";
  const direction: SortDirection = dir === "asc" || dir === "desc" ? dir : bestFirstDirection(resolved);
  return { sort: resolved, dir: direction };
}
