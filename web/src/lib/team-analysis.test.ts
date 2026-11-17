import assert from "node:assert/strict";
import test from "node:test";
import { boundedRatingHistory, nationalRanks, weeklyMovement, type AnalysisRating, type RatingHistoryPeriod } from "./team-analysis.ts";

const row = (team: string, overallRating: number): AnalysisRating => ({
  team, overallRating, offenseRating: overallRating, defenseRating: overallRating,
  wins: null, losses: null, completedGames: null, waa: null, sor: null, sorRank: null,
  sosPlayedAverage: null, sosRemainingAverage: null, sosFullAverage: null,
});
const period = (id: string, postWeek: number, cutoffUtc: string, ratings: AnalysisRating[], sourceManifestSha256 = "src-a"): RatingHistoryPeriod => ({
  period: { id, label: id, postWeek, sourceManifestSha256, cutoffUtc }, ratings,
});

test("nationalRanks gives tied teams the same rank and skips the next", () => {
  const ranks = nationalRanks([row("A", 3), row("B", 2), row("C", 2), row("D", 1)], "overall");
  assert.deepEqual([...ranks], [["A", 1], ["B", 2], ["C", 2], ["D", 4]]);
});

test("weeklyMovement reports rating change and rank improvement across consecutive weeks", () => {
  const previous = period("w1", 1, "2026-09-07T00:00:00.000Z", [row("A", 1), row("B", 2)]);
  const current = period("w2", 2, "2026-09-14T00:00:00.000Z", [row("A", 3), row("B", 2)]);
  const movement = weeklyMovement(current, [previous, current]);
  assert.deepEqual(movement.get("A"), { change: 2, rankChange: 1 });
  assert.deepEqual(movement.get("B"), { change: 0, rankChange: -1 });
});

test("weeklyMovement is empty when the previous week is ambiguous, missing or from another source", () => {
  const current = period("w2", 2, "2026-09-14T00:00:00.000Z", [row("A", 3)]);
  const prior = (id: string, source = "src-a") => period(id, 1, "2026-09-07T00:00:00.000Z", [row("A", 1)], source);
  assert.equal(weeklyMovement(current, [prior("w1a"), prior("w1b")]).size, 0, "two candidate generations");
  assert.equal(weeklyMovement(current, [current]).size, 0, "no previous week (gap)");
  assert.equal(weeklyMovement(current, [period("w0", 0, "2026-08-30T00:00:00.000Z", [row("A", 0)])]).size, 0, "week gap");
  assert.equal(weeklyMovement(current, [prior("w1x", "src-b")]).size, 0, "different source");
  assert.equal(weeklyMovement(period("pre", 0, "2026-08-30T00:00:00.000Z", [row("A", 0)]), [prior("w1a")]).size, 0, "preseason");
});

test("boundedRatingHistory drops future and other-source periods and keeps the selected one", () => {
  const selected = period("w2", 2, "2026-09-14T00:00:00.000Z", [row("A", 3)]);
  const history = [
    period("w1", 1, "2026-09-07T00:00:00.000Z", [row("A", 1)]),
    period("w3", 3, "2026-09-21T00:00:00.000Z", [row("A", 4)]),
    period("w1-other", 1, "2026-09-07T00:00:00.000Z", [row("A", 9)], "src-b"),
  ];
  const bounded = boundedRatingHistory(history, selected);
  assert.deepEqual(bounded.map((item) => item.period.id), ["w1", "w2"]);
  assert.equal(boundedRatingHistory(history, period("preseason", 0, "2026-08-01T00:00:00.000Z", [])).length, 1);
});
