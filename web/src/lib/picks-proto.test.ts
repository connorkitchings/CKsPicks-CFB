import assert from "node:assert/strict";
import test from "node:test";

import {
  edgeTier,
  hasLean,
  leanFor,
  overallRanks,
  sortGames,
  topLeans,
  winRatePct,
} from "./picks-proto.ts";
import type { Game } from "./queries.ts";

function game(over: Record<string, unknown>): Game {
  return {
    gameId: 1,
    season: 2026,
    week: 5,
    startDate: new Date("2026-10-03T16:00:00Z"),
    homeTeam: "Home",
    awayTeam: "Away",
    homeTeamSpreadLine: -3.5,
    totalLine: 50.5,
    updatedAt: new Date("2026-09-30T00:00:00Z"),
    homePoints: null,
    awayPoints: null,
    homeRecord: null,
    awayRecord: null,
    publicationMode: "predictions",
    runId: "r",
    runState: "frozen",
    predictedSpread: 6.5,
    predictedTotal: 55,
    predictedSpreadStdDev: null,
    predictedTotalStdDev: null,
    spreadLean: "home",
    totalLean: "over",
    edgeSpread: 3,
    edgeTotal: 4.5,
    highConfidence: false,
    systemName: "x",
    modelId: "m",
    regime: null,
    homeCompletedGames: 4,
    awayCompletedGames: 4,
    spreadModelVersion: null,
    totalModelVersion: null,
    spreadResult: null,
    totalResult: null,
    ...over,
  } as Game;
}

test("edge tiers follow the spread and total thresholds", () => {
  assert.equal(edgeTier("spread", null), 0);
  assert.equal(edgeTier("spread", 0), 0);
  assert.equal(edgeTier("spread", 3), 1);
  assert.equal(edgeTier("spread", 3.1), 2);
  assert.equal(edgeTier("spread", 8), 2);
  assert.equal(edgeTier("spread", 8.1), 3);
  assert.equal(edgeTier("total", 2), 1);
  assert.equal(edgeTier("total", 7.1), 3);
});

test("leanFor labels the pick side with a positive edge", () => {
  const home = leanFor(game({}), "spread");
  assert.equal(home?.pick, "Home -3.5");
  assert.equal(home?.edge, 3);
  const away = leanFor(game({ spreadLean: "away", edgeSpread: -4.2 }), "spread");
  assert.equal(away?.pick, "Away +3.5");
  assert.equal(away?.edge, 4.2);
  assert.equal(leanFor(game({ totalLean: "under" }), "total")?.pick, "Under 50.5");
});

test("no lean when the lean or the line is missing, and for market games", () => {
  assert.equal(leanFor(game({ spreadLean: null }), "spread"), null);
  assert.equal(leanFor(game({ homeTeamSpreadLine: null }), "spread"), null);
  assert.equal(leanFor(game({ totalLine: null }), "total"), null);
  const market = { ...game({}), publicationMode: "market" } as Game;
  assert.equal(leanFor(market, "spread"), null);
  assert.equal(hasLean(game({ spreadLean: null, totalLean: null })), false);
  assert.equal(hasLean(game({ spreadLean: null })), true);
});

test("topLeans ranks by edge and skips finished games", () => {
  const games = [
    game({ gameId: 1, edgeSpread: 2 }),
    game({ gameId: 2, edgeSpread: 9 }),
    game({ gameId: 3, edgeSpread: 12, homePoints: 21, awayPoints: 17 }),
    game({ gameId: 4, edgeSpread: 5, spreadLean: null }),
  ];
  assert.deepEqual(topLeans(games, "spread", 5).map((l) => l.game.gameId), [2, 1]);
  assert.deepEqual(topLeans(games, "spread", 1).map((l) => l.game.gameId), [2]);
});

test("sortGames puts the biggest edge first and no-lean games last", () => {
  const games = [
    game({ gameId: 1, edgeSpread: 2, edgeTotal: 1 }),
    game({ gameId: 2, spreadLean: null, totalLean: null }),
    game({ gameId: 3, edgeSpread: 1, edgeTotal: 6 }),
  ];
  assert.deepEqual(sortGames(games, "bestEdge").map((g) => g.gameId), [3, 1, 2]);
  assert.deepEqual(sortGames(games, "spreadEdge").map((g) => g.gameId), [1, 3, 2]);
});

test("win rate excludes pushes and is null with no decisions", () => {
  assert.equal(winRatePct(0, 0), null);
  assert.equal(winRatePct(1, 1), 50);
  assert.equal(Math.round((winRatePct(93, 103) ?? 0) * 10) / 10, 47.4);
});

test("overallRanks is 1-based, best rating first", () => {
  const ranks = overallRanks([
    { team: "B", overallRating: 1 },
    { team: "A", overallRating: 4 },
  ]);
  assert.deepEqual(ranks, { A: 1, B: 2 });
});
