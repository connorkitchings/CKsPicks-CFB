import assert from "node:assert/strict";
import test from "node:test";
import {
  joinTeamResume,
  mapResumePeriodRow,
  mapTeamResumeRow,
  resumeFactsByPeriod,
  RESUME_PERIOD_COLUMNS,
  TEAM_RESUME_COLUMNS,
  type ResumePeriodRow,
} from "./team-resume.ts";
import type { Rating } from "./rating-periods.ts";

const PERIOD = `${"a".repeat(64)}@2026-10-18T14:00:00.000Z`;
const OTHER_PERIOD = `${"b".repeat(64)}@2026-10-11T15:00:00.000Z`;

const rating = (team: string): Rating => ({
  team,
  week: 7,
  cutoffUtc: new Date("2026-10-18T14:00:00.000Z"),
  offenseRating: 1,
  offenseVariance: 0.1,
  defenseRating: 1,
  defenseVariance: 0.1,
  overallRating: 2,
  overallVariance: 0.1,
  fallbackReason: null,
});

/** One raw `SELECT TEAM_RESUME_COLUMNS` row, as the database returns it. */
const rawRow = (overrides: Record<string, unknown> = {}): Record<string, unknown> => ({
  period_id: PERIOD,
  team: "Ohio State",
  wins: 6,
  losses: 1,
  completed_games: 7,
  scheduled_games: 12,
  sos_played_elite: 61.5,
  sos_remaining_elite: 58.25,
  sos_full_elite: 60,
  sos_played_average: 44.1,
  sos_remaining_average: 40.2,
  sos_full_average: 42.6,
  sor: 87.3,
  sor_rank: 3,
  waa: 4.2,
  ...overrides,
});

test("resume rows attach by exact period and team, and absent teams get null", () => {
  const rows = [
    mapTeamResumeRow(rawRow()),
    mapTeamResumeRow(rawRow({ period_id: OTHER_PERIOD, team: "Texas", wins: 0 })),
  ];
  const [ohio, texas] = joinTeamResume([rating("Ohio State"), rating("Texas"), rating("Oregon")], PERIOD, rows);
  assert.equal(ohio.wins, 6);
  assert.equal(ohio.completedGames, 7);
  assert.equal(ohio.sosPlayedElite, 61.5);
  assert.equal(ohio.sorRank, 3);
  assert.equal(ohio.sor, 87.3);
  assert.equal(ohio.waa, 4.2);
  assert.equal(ohio.overallRating, 2, "original rating fields are kept");
  assert.equal(texas.wins, null, "a row from another period never matches");
  assert.equal(texas.sor, null);
  const oregon = joinTeamResume([rating("Oregon")], PERIOD, rows)[0];
  assert.equal(oregon.wins, null, "a team with no row gets null");
  assert.equal(Object.hasOwn(ohio, "periodId"), false, "row identity is not attached to the rating");
});

test("missing projection table yields null résumé fields on every rating", () => {
  const [ohio] = joinTeamResume([rating("Ohio State")], PERIOD, null);
  assert.equal(ohio.team, "Ohio State");
  assert.equal(ohio.wins, null);
  assert.equal(ohio.sosFullAverage, null);
  assert.equal(ohio.waa, null);
});

test("present but empty projection yields null résumé fields on every rating", () => {
  const [ohio] = joinTeamResume([rating("Ohio State")], PERIOD, []);
  assert.equal(ohio.wins, null);
  assert.equal(ohio.sorRank, null);
});

test("null SOR and WAA stay null while the other fields map", () => {
  const row = mapTeamResumeRow(rawRow({ period_id: "preseason", sor: null, sor_rank: null, waa: null }));
  assert.equal(row.sor, null);
  assert.equal(row.sorRank, null);
  assert.equal(row.waa, null);
  assert.equal(row.wins, 6);
  const [ohio] = joinTeamResume([rating("Ohio State")], "preseason", [row]);
  assert.equal(ohio.sor, null);
  assert.equal(ohio.waa, null);
  assert.equal(ohio.sosPlayedAverage, 44.1);
});

test("mapping rejects rows without a period or team", () => {
  assert.throws(() => mapTeamResumeRow(rawRow({ team: null })), /Invalid season_release_team_resume row/);
  assert.throws(() => mapTeamResumeRow(rawRow({ period_id: undefined })), /Invalid season_release_team_resume row/);
});

test("selected columns cover every résumé field exactly once", () => {
  assert.ok(TEAM_RESUME_COLUMNS.includes("sos_played_elite"));
  assert.ok(TEAM_RESUME_COLUMNS.includes("sor_rank"));
  assert.equal(new Set(TEAM_RESUME_COLUMNS).size, TEAM_RESUME_COLUMNS.length);
});

const WEEK_7 = `${"c".repeat(64)}@2026-10-18T14:00:00.000Z`;
const WEEK_6 = `${"c".repeat(64)}@2026-10-11T15:00:00.000Z`;
const PRESEASON_ID = "preseason";

const periodRow = (periodId: string, postWeek: number | null, completedGames: number): ResumePeriodRow =>
  ({ periodId, postWeek, completedGames });

test("period facts take post_week from the rows and halve the summed team game counts", () => {
  // Each completed game between two FBS teams has one row per team, so four rows
  // summing to 26 completed team games describe 13 games.
  const facts = resumeFactsByPeriod([
    periodRow(WEEK_7, 7, 7),
    periodRow(WEEK_7, 7, 7),
    periodRow(WEEK_7, 7, 6),
    periodRow(WEEK_7, 7, 6),
    periodRow(WEEK_6, 6, 5),
    periodRow(WEEK_6, 6, 5),
  ]);
  assert.deepEqual(facts.get(WEEK_7), { postWeek: 7, games: 13 });
  assert.deepEqual(facts.get(WEEK_6), { postWeek: 6, games: 5 });
});

test("a preseason period, whose post_week is null, gets no facts and keeps the preseason label", () => {
  const facts = resumeFactsByPeriod([periodRow(PRESEASON_ID, null, 0), periodRow(PRESEASON_ID, null, 0)]);
  assert.equal(facts.has(PRESEASON_ID), false);
});

test("no résumé rows yield no period facts, so every period falls back to its date label", () => {
  assert.equal(resumeFactsByPeriod([]).size, 0);
});

test("period row mapping reads the snake_case columns and rejects a row without a period", () => {
  assert.deepEqual(RESUME_PERIOD_COLUMNS, ["period_id", "post_week", "completed_games"]);
  assert.deepEqual(
    mapResumePeriodRow({ period_id: WEEK_7, post_week: 7, completed_games: 6 }),
    { periodId: WEEK_7, postWeek: 7, completedGames: 6 },
  );
  assert.equal(
    mapResumePeriodRow({ period_id: PRESEASON_ID, post_week: null, completed_games: 0 }).postWeek,
    null,
  );
  assert.throws(
    () => mapResumePeriodRow({ period_id: undefined, post_week: 7, completed_games: 6 }),
    /Invalid season_release_team_resume row/,
  );
});
