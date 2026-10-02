/**
 * SQL for "another team has the same national rank" (a tie; the publisher
 * ranks ties by minimum rank). Dependency-free so it can be unit tested.
 *
 * The outer columns are written with the table name on purpose: drizzle renders
 * a single-table select's columns unqualified, and inside the subquery an
 * unqualified `season` binds to the inner alias, which compares a row with
 * itself and makes EXISTS always false. EXISTS short-circuits on the first match.
 */
export type RankedTable = "team_season_stats" | "team_possession_stats";

export function tiedExistsSql(table: RankedTable): string {
  return `EXISTS (
    SELECT 1 FROM ${table} s2
    WHERE s2.season = ${table}.season AND s2.as_of_week = ${table}.as_of_week
      AND s2.role = ${table}.role AND s2.metric = ${table}.metric
      AND s2.rank = ${table}.rank AND s2.team <> ${table}.team
  )`;
}
