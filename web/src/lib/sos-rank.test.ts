import assert from "node:assert/strict";
import test from "node:test";
import { bestFirstDirection, competitionRanks, parseRatingsSort, rankSosByTeam } from "./sos-rank.ts";

test("competitionRanks ranks the highest value first", () => {
  assert.deepEqual(competitionRanks([50, 70, 60]), [3, 1, 2]);
});

test("competitionRanks gives tied values the lowest rank and skips the next rank", () => {
  assert.deepEqual(competitionRanks([70, 60, 60, 50]), [1, 2, 2, 4]);
  assert.deepEqual(competitionRanks([60, 60, 60]), [1, 1, 1]);
});

test("competitionRanks leaves null, undefined and non-finite values unranked without taking a place", () => {
  assert.deepEqual(competitionRanks([null, 70, undefined, 60, Number.NaN]), [null, 1, null, 2, null]);
  assert.deepEqual(competitionRanks([]), []);
});

test("rankSosByTeam ranks played, remaining and full columns independently", () => {
  const ranks = rankSosByTeam([
    { team: "A", sosPlayedAverage: 50, sosRemainingAverage: 60, sosFullAverage: 55 },
    { team: "B", sosPlayedAverage: 60, sosRemainingAverage: 50, sosFullAverage: 55 },
    { team: "C", sosPlayedAverage: 40, sosRemainingAverage: 70, sosFullAverage: 65 },
  ]);
  assert.deepEqual(ranks.get("A"), { played: 2, remaining: 2, full: 2 });
  assert.deepEqual(ranks.get("B"), { played: 1, remaining: 3, full: 2 });
  assert.deepEqual(ranks.get("C"), { played: 3, remaining: 1, full: 1 });
});

test("rankSosByTeam leaves a null SOS value unranked in that column only", () => {
  const ranks = rankSosByTeam([
    { team: "X", sosPlayedAverage: null, sosRemainingAverage: 40, sosFullAverage: 60 },
    { team: "Y", sosPlayedAverage: 50, sosRemainingAverage: null, sosFullAverage: 50 },
  ]);
  assert.deepEqual(ranks.get("X"), { played: null, remaining: 1, full: 1 });
  assert.deepEqual(ranks.get("Y"), { played: 1, remaining: null, full: 2 });
});

test("rankSosByTeam returns a team's rank from the whole period, not from a filtered subset", () => {
  const period = [
    { team: "Alpha", sosFullAverage: 70 },
    { team: "Beta", sosFullAverage: 60 },
    { team: "Gamma", sosFullAverage: 50 },
  ];
  const wholePeriodRank = rankSosByTeam(period).get("Gamma")?.full;
  const searchedRank = rankSosByTeam(period.filter((row) => row.team === "Gamma")).get("Gamma")?.full;
  assert.equal(wholePeriodRank, 3);
  assert.equal(searchedRank, 1);
});

test("bestFirstDirection opens rating sorts highest first and rank sorts at rank 1", () => {
  assert.equal(bestFirstDirection("overall"), "desc");
  assert.equal(bestFirstDirection("offense"), "desc");
  assert.equal(bestFirstDirection("defense"), "desc");
  assert.equal(bestFirstDirection("sor"), "asc");
  assert.equal(bestFirstDirection("sos_played"), "asc");
  assert.equal(bestFirstDirection("sos_remaining"), "asc");
  assert.equal(bestFirstDirection("sos_full"), "asc");
});

test("parseRatingsSort maps the legacy sos value to SOS Full", () => {
  assert.deepEqual(parseRatingsSort("sos", undefined), { sort: "sos_full", dir: "asc" });
  assert.deepEqual(parseRatingsSort("sos_played", undefined), { sort: "sos_played", dir: "asc" });
});

test("parseRatingsSort falls back to Overall for missing and retired sorts", () => {
  assert.deepEqual(parseRatingsSort(undefined, undefined), { sort: "overall", dir: "desc" });
  assert.deepEqual(parseRatingsSort("", undefined), { sort: "overall", dir: "desc" });
  assert.deepEqual(parseRatingsSort("waa", undefined), { sort: "overall", dir: "desc" });
});

test("parseRatingsSort honours a valid direction and replaces an unknown one with the sort default", () => {
  assert.deepEqual(parseRatingsSort("overall", "asc"), { sort: "overall", dir: "asc" });
  assert.deepEqual(parseRatingsSort("sos_full", "desc"), { sort: "sos_full", dir: "desc" });
  assert.deepEqual(parseRatingsSort("sor", "sideways"), { sort: "sor", dir: "asc" });
});

test("competitionRanks gives teams with equal overall ratings the same rank", () => {
  assert.deepEqual(competitionRanks([0.53, 1.2, 0.53, -0.4]), [2, 1, 2, 4]);
});
