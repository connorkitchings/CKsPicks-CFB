import assert from "node:assert/strict";
import test from "node:test";
import { teamRankHistory } from "./team-rank-history.ts";

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
