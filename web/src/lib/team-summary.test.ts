import assert from "node:assert/strict";
import test from "node:test";
import type { Rating } from "./rating-periods.ts";
import { buildTeamSummary } from "./team-summary.ts";

const rating = (team: string, overall: number, over: Partial<Rating> = {}): Rating => ({
  team, week: 4, cutoffUtc: new Date(0), offenseRating: overall, offenseVariance: 1, defenseRating: -overall,
  defenseVariance: 1, overallRating: overall, overallVariance: 1, fallbackReason: null, ...over,
});

test("buildTeamSummary ranks the team against the whole field", () => {
  const field = [rating("A", 3), rating("B", 2, { waa: 1 }), rating("C", 1, { waa: 2 })];
  const summary = buildTeamSummary(field, "B", [])!;
  assert.equal(summary.overallRank, 2);
  assert.equal(summary.offenseRank, 2);
  assert.equal(summary.defenseRank, 2);
  assert.equal(summary.waaRank, 2);
});

test("buildTeamSummary leaves a rank null when the team has no value", () => {
  const field = [rating("A", 3, { waa: 1 }), rating("B", 2)];
  assert.equal(buildTeamSummary(field, "B", [])!.waaRank, null);
});

test("buildTeamSummary reports the move between the last two stored weeks", () => {
  const history = [{ week: 1, rating: 1, rank: 90 }, { week: 2, rating: 1.5, rank: 80 }, { week: 3, rating: 1.25, rank: 84 }];
  const summary = buildTeamSummary([rating("A", 1)], "A", history)!;
  assert.deepEqual(summary.change, { spots: -4, delta: -0.25 });
});

test("buildTeamSummary has no move before a second week", () => {
  assert.equal(buildTeamSummary([rating("A", 1)], "A", [{ week: 0, rating: 1, rank: 1 }])!.change, null);
});

test("buildTeamSummary is null for a team without a row", () => {
  assert.equal(buildTeamSummary([rating("A", 1)], "Z", []), null);
});
