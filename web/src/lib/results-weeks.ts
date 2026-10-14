import { isDisplayOnly } from "./display-only.ts";
import { isSelectableRun } from "./run-selection.ts";

/** A season's selected run for one week, plus how many of its games have a result row. */
export type SelectedWeekRun = {
  week: number;
  state: string;
  evidenceClass: string | null;
  modelId: string | null;
  validation: unknown;
  gradedGames: number;
};

/**
 * Weeks the Results page lists, ascending and de-duplicated. A scored run
 * always qualifies. A display-only run is never frozen or scored, so it
 * qualifies while `published` once at least one of its games has a final.
 */
export function selectGradedWeeks(rows: SelectedWeekRun[]): number[] {
  const weeks = new Set<number>();
  for (const row of rows) {
    if (!isSelectableRun(row)) continue;
    const gradedDisplayOnly = row.state === "published"
      && isDisplayOnly(row.validation)
      && row.gradedGames > 0;
    if (row.state === "scored" || gradedDisplayOnly) weeks.add(row.week);
  }
  return [...weeks].sort((a, b) => a - b);
}
