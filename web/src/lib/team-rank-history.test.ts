import assert from "node:assert/strict";
import test from "node:test";
import { teamRankHistory, trendAxis, trendWeekLabels } from "./team-rank-history.ts";

const row = (week: number, team: string, overallRating: number) => ({ week, team, overallRating });

test("teamRankHistory ranks the team against every team of each week", () => {
  const rows = [row(0, "A", 1), row(0, "B", 3), row(1, "A", 5), row(1, "B", 3), row(1, "C", 4)];
  assert.deepEqual(teamRankHistory(rows, "A"), [
    { week: 0, rating: 1, rank: 2 },
    { week: 1, rating: 5, rank: 1 },
  ]);
});

test("teamRankHistory shares the lowest rank between tied ratings", () => {
  const rows = [row(0, "A", 2), row(0, "B", 2), row(0, "C", 1)];
  assert.equal(teamRankHistory(rows, "B")[0].rank, 1);
  assert.equal(teamRankHistory(rows, "C")[0].rank, 3);
});

test("teamRankHistory skips weeks without the team and sorts by week", () => {
  const rows = [row(2, "A", 1), row(1, "B", 1), row(0, "A", 1)];
  assert.deepEqual(teamRankHistory(rows, "A").map((point) => point.week), [0, 2]);
});

test("teamRankHistory is empty for an unknown team", () => {
  assert.deepEqual(teamRankHistory([row(0, "A", 1)], "Z"), []);
});

test("trendAxis gives round rating ticks with a zero line when the range spans zero", () => {
  const axis = trendAxis([0.1, -0.2, -0.4, -0.7, -0.36], "rating");
  assert.ok(axis.ticks.includes(0));
  assert.ok(axis.ticks.every((tick) => Math.abs(tick * 10 - Math.round(tick * 10)) < 1e-9));
  assert.ok(axis.lo < -0.7 && axis.hi > 0.1);
  assert.ok(axis.ticks.every((tick) => tick >= axis.lo && tick <= axis.hi));
});

test("trendAxis gives whole round rank ticks that never pass #1", () => {
  const axis = trendAxis([84, 92, 97, 88], "rank");
  assert.deepEqual(axis.ticks, [85, 90, 95]);
  assert.equal(trendAxis([1, 2], "rank").lo, 1);
  assert.ok(trendAxis([5, 5], "rank").ticks.every(Number.isInteger));
});

test("trendWeekLabels always labels the first and last week and keeps labels apart", () => {
  const weeks = [0, 1, 2, 3, 4, 5, 6, 7];
  const labels = trendWeekLabels(weeks, 268, 52);
  assert.equal(labels[0], 0);
  assert.equal(labels[labels.length - 1], 7);
  for (let i = 1; i < labels.length; i++) assert.ok(((labels[i] - labels[i - 1]) / 7) * 268 >= 52);
});

test("trendAxis keeps at most five ticks", () => {
  for (const [values, measure] of [[[0.1, -0.7], "rating"], [[3, 120], "rank"], [[-4, 6], "rating"]] as const) {
    assert.ok(trendAxis(values, measure).ticks.length <= 5, `${values}`);
  }
});

test("trendWeekLabels handles one and two points and weeks with gaps", () => {
  assert.deepEqual(trendWeekLabels([3], 268, 52), [3]);
  assert.deepEqual(trendWeekLabels([0, 1], 268, 52), [0, 1]);
  assert.ok(trendWeekLabels([0, 3, 7], 268, 52).every((week) => [0, 3, 7].includes(week)));
});
