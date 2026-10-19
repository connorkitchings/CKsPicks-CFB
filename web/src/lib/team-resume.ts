/**
 * Pure mapping and join for `season_release_team_resume` rows. Every value is copied
 * from the projection as stored; nothing is computed here. Dependency-free (no database)
 * so the behavioral tests run under plain `node:test`.
 */
import type { Rating, ResumePeriodFacts } from "./rating-periods.ts";

/** Résumé and strength-of-schedule fields, in camelCase as they appear on `Rating`. */
export const TEAM_RESUME_KEYS = [
  "wins", "losses", "completedGames", "scheduledGames",
  "sosPlayedElite", "sosRemainingElite", "sosFullElite",
  "sosPlayedAverage", "sosRemainingAverage", "sosFullAverage",
  "sor", "sorRank", "waa",
] as const;

export type TeamResumeFields = Record<(typeof TEAM_RESUME_KEYS)[number], number | null>;

/** One projection row for a team and period, with its fields mapped to camelCase. */
export type TeamResumeRow = TeamResumeFields & { periodId: string; team: string };

const snakeCase = (key: string) => key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);

/** Columns to select from `season_release_team_resume`, in snake_case. */
export const TEAM_RESUME_COLUMNS = ["period_id", "team", ...TEAM_RESUME_KEYS.map(snakeCase)] as const;

const numberOrNull = (value: unknown): number | null =>
  value === null || value === undefined ? null : Number(value);

/** Maps one raw `SELECT TEAM_RESUME_COLUMNS` row to a typed row. */
export function mapTeamResumeRow(row: Record<string, unknown>): TeamResumeRow {
  if (typeof row.period_id !== "string" || typeof row.team !== "string") {
    throw new Error("Invalid season_release_team_resume row");
  }
  const fields = Object.fromEntries(
    TEAM_RESUME_KEYS.map((key) => [key, numberOrNull(row[snakeCase(key)])]),
  ) as TeamResumeFields;
  return { ...fields, periodId: row.period_id, team: row.team };
}

const ABSENT: TeamResumeFields = Object.fromEntries(
  TEAM_RESUME_KEYS.map((key) => [key, null]),
) as TeamResumeFields;

/** Columns read per team row to derive each period's label. */
export const RESUME_PERIOD_COLUMNS = ["period_id", "post_week", "completed_games"] as const;

export type ResumePeriodRow = { periodId: string; postWeek: number | null; completedGames: number };

/** Maps one raw `SELECT RESUME_PERIOD_COLUMNS` row to a typed row. */
export function mapResumePeriodRow(row: Record<string, unknown>): ResumePeriodRow {
  const completedGames = Number(row.completed_games);
  if (typeof row.period_id !== "string" || !Number.isInteger(completedGames)) {
    throw new Error("Invalid season_release_team_resume row");
  }
  return { periodId: row.period_id, postWeek: numberOrNull(row.post_week), completedGames };
}

/**
 * Period facts from the team rows of each period. `post_week` is the same on every row of
 * a period, so the first non-null value is used; a preseason period has none and gets no
 * facts, so it keeps its "Preseason" label. `completed_games` counts per team, and a
 * completed game between two FBS teams appears in both teams' rows, so the period's game
 * count is the sum halved. Games against non-FBS opponents have no row and are not counted.
 */
export function resumeFactsByPeriod(rows: readonly ResumePeriodRow[]): Map<string, ResumePeriodFacts> {
  const totals = new Map<string, { postWeek: number | null; completed: number }>();
  for (const row of rows) {
    const total = totals.get(row.periodId) ?? { postWeek: null, completed: 0 };
    total.postWeek ??= row.postWeek;
    total.completed += row.completedGames;
    totals.set(row.periodId, total);
  }
  const facts = new Map<string, ResumePeriodFacts>();
  for (const [periodId, { postWeek, completed }] of totals) {
    if (postWeek !== null) facts.set(periodId, { postWeek, games: completed / 2 });
  }
  return facts;
}

/**
 * Attaches the résumé fields of `periodId` to each rating by team. `rows` is null when
 * the projection is unavailable (no release, or migration 0028 not applied); every
 * rating then keeps null fields instead of failing. Rows for other periods never match.
 */
export function joinTeamResume(
  ratings: Rating[],
  periodId: string,
  rows: readonly TeamResumeRow[] | null,
): Rating[] {
  const byTeam = new Map<string, TeamResumeFields>();
  for (const row of rows ?? []) {
    if (row.periodId !== periodId) continue;
    byTeam.set(row.team, Object.fromEntries(TEAM_RESUME_KEYS.map((key) => [key, row[key]])) as TeamResumeFields);
  }
  return ratings.map((rating) => ({ ...rating, ...(byTeam.get(rating.team) ?? ABSENT) }));
}
