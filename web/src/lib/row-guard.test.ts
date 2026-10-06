import test from "node:test";
import assert from "node:assert/strict";
import {
  PERFORMANCE_DETAIL_SPEC,
  PREDICTION_GAME_SPEC,
  RATING_SPEC,
  RowContractError,
  TEAM_STAT_RULES,
  TEAM_STAT_SPEC,
  checkRows,
  guardRows,
} from "./row-guard.ts";

const quiet = <T>(fn: () => T): T => {
  const original = console.error;
  console.error = () => {};
  try {
    return fn();
  } finally {
    console.error = original;
  }
};

const stat = (over: Record<string, unknown> = {}) => ({
  team: "Fargo State",
  role: "offense",
  metric: "ppp",
  value: 2.1,
  n: 40,
  games: 5,
  rank: 3,
  cohortSize: 130,
  ...over,
});

test("valid rows are returned unchanged, including allowed nulls", () => {
  const rows = [stat(), stat({ value: null, rank: null, cohortSize: null })];
  assert.equal(guardRows("team_stats", rows, TEAM_STAT_SPEC, TEAM_STAT_RULES), rows);
});

test("a null in a required field is a violation, never a zero", () => {
  const rows = [stat({ games: null })];
  const { violations, total } = checkRows(rows, TEAM_STAT_SPEC);
  assert.equal(total, 1);
  assert.deepEqual(violations[0], { index: 0, field: "games", reason: "null in a required field" });
  assert.equal(rows[0].games, null); // the guard never repairs data
});

test("NaN and Infinity are rejected as numbers", () => {
  assert.equal(checkRows([stat({ value: Number.NaN })], TEAM_STAT_SPEC).total, 1);
  assert.equal(checkRows([stat({ value: Number.POSITIVE_INFINITY })], TEAM_STAT_SPEC).total, 1);
  assert.equal(checkRows([stat({ value: "2.1" })], TEAM_STAT_SPEC).total, 1);
});

test("a missing field, an unknown enum value and a non-integer are reported", () => {
  const { violations } = checkRows(
    [{ team: "A", role: "special", metric: "m", n: 1, games: 2.5 }],
    TEAM_STAT_SPEC,
  );
  const reasons = Object.fromEntries(violations.map((v) => [v.field, v.reason]));
  assert.match(reasons.role, /not one of/);
  assert.equal(reasons.games, "not an integer");
  assert.equal(reasons.value, "missing");
});

test("rank must sit inside its cohort", () => {
  const rule = (row: Record<string, unknown>) => TEAM_STAT_RULES[0](row);
  assert.equal(rule(stat()), null);
  assert.equal(rule(stat({ rank: null, cohortSize: null })), null);
  assert.equal(rule(stat({ rank: 0 })), "rank below 1");
  assert.equal(rule(stat({ rank: 200 })), "rank above the cohort size");
  assert.equal(rule(stat({ cohortSize: null })), "rank without a cohort size");
});

test("guardRows throws a RowContractError naming the label and the first problems", () => {
  const error = quiet(() => {
    try {
      guardRows("matchup_team_stats", [stat(), stat({ rank: 999 })], TEAM_STAT_SPEC, TEAM_STAT_RULES);
    } catch (e) {
      return e;
    }
  });
  assert.ok(error instanceof RowContractError);
  assert.match((error as Error).message, /matchup_team_stats: 1 contract violation/);
  assert.equal((error as RowContractError).violations[0].index, 1);
});

test("reports are capped but the total is exact", () => {
  const rows = Array.from({ length: 50 }, () => stat({ games: null }));
  const { violations, total } = checkRows(rows, TEAM_STAT_SPEC);
  assert.equal(total, 50);
  assert.equal(violations.length, 20);
});

test("dates must be valid Date objects", () => {
  const rating = {
    team: "A", week: 5, cutoffUtc: new Date("2026-10-01T00:00:00Z"),
    offenseRating: 1, offenseVariance: 0.5, defenseRating: -1, defenseVariance: 0.5,
    overallRating: 0, overallVariance: 1,
  };
  assert.equal(checkRows([rating], RATING_SPEC).total, 0);
  assert.equal(checkRows([{ ...rating, cutoffUtc: new Date("nope") }], RATING_SPEC).total, 1);
  assert.equal(checkRows([{ ...rating, overallRating: null }], RATING_SPEC).total, 1);
});

test("prediction and performance rows allow null leans and grades but not null identities", () => {
  const game = {
    gameId: 1, week: 1, startDate: new Date(), homeTeam: "A", awayTeam: "B",
    homeTeamSpreadLine: null, totalLine: null, predictedSpread: -3.2, predictedTotal: 50.1,
    spreadLean: null, totalLean: null, edgeSpread: 0.4, edgeTotal: 0.1, highConfidence: false,
    spreadResult: null, totalResult: null,
  };
  assert.equal(checkRows([game], PREDICTION_GAME_SPEC).total, 0);
  assert.equal(checkRows([{ ...game, gameId: null }], PREDICTION_GAME_SPEC).total, 1);
  assert.equal(checkRows([{ ...game, spreadLean: "push" }], PREDICTION_GAME_SPEC).total, 1);
  const detail = {
    evidenceClass: "replay", week: 1, gameId: 1, runId: "run-1", startDate: new Date(), homeTeam: "A", awayTeam: "B",
    predictedSpread: null, predictedTotal: null, predictedSpreadStdDev: null, predictedTotalStdDev: null,
    spreadLean: "away", totalLean: null, spreadResult: "win", totalResult: null, highConfidence: true,
  };
  assert.equal(checkRows([detail], PERFORMANCE_DETAIL_SPEC).total, 0);
  assert.equal(checkRows([{ ...detail, evidenceClass: "draft" }], PERFORMANCE_DETAIL_SPEC).total, 1);
});

test("the UI-test fixtures satisfy the row contracts (CFB_UI_TEST_MODE=1 stays valid)", async () => {
  const { v5PerformanceDetailFixture } = await import("../test/fixtures/publication.ts");
  const detailRows = v5PerformanceDetailFixture.gradedGames.map((g) => ({
    evidenceClass: g.evidenceClass,
    week: g.week,
    gameId: g.gameId,
    runId: g.runId,
    startDate: g.startDate,
    homeTeam: g.homeTeam,
    awayTeam: g.awayTeam,
    predictedSpread: g.predictedSpread,
    predictedTotal: g.predictedTotal,
    predictedSpreadStdDev: null,
    predictedTotalStdDev: null,
    spreadLean: g.spreadLean,
    totalLean: g.totalLean,
    spreadResult: g.spreadResult,
    totalResult: g.totalResult,
    highConfidence: g.highConfidence,
  }));
  assert.equal(checkRows(detailRows, PERFORMANCE_DETAIL_SPEC).total, 0);
});
