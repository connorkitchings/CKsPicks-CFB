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

import {
  coverMargin,
  gradeFromMargin,
  matchesResult,
  sortResults,
  topResults,
  weekRecord,
} from "./picks-proto.ts";

function finalGame(over: Record<string, unknown>): Game {
  return game({ homePoints: 24, awayPoints: 17, ...over });
}

test("coverMargin is positive when the lean side covered", () => {
  // Home -3.5 lean, home wins by 7 -> covers by 3.5.
  assert.equal(coverMargin(finalGame({}), "spread"), 3.5);
  // Away lean at +3.5 (home line -3.5): home wins by 7 -> away misses by 3.5.
  assert.equal(coverMargin(finalGame({ spreadLean: "away" }), "spread"), -3.5);
  // Over 50.5, final total 41 -> misses by 9.5; under covers by 9.5.
  assert.equal(coverMargin(finalGame({}), "total"), -9.5);
  assert.equal(coverMargin(finalGame({ totalLean: "under" }), "total"), 9.5);
  // Not final, or no lean -> null.
  assert.equal(coverMargin(game({}), "spread"), null);
  assert.equal(coverMargin(finalGame({ spreadLean: null }), "spread"), null);
});

test("gradeFromMargin maps sign to win, loss and push", () => {
  assert.equal(gradeFromMargin(0.5), "win");
  assert.equal(gradeFromMargin(-0.5), "loss");
  assert.equal(gradeFromMargin(0), "push");
  assert.equal(gradeFromMargin(null), null);
});

test("weekRecord tallies recorded grades per bet type", () => {
  const games = [
    finalGame({ gameId: 1, spreadResult: "win", totalResult: "loss" }),
    finalGame({ gameId: 2, spreadResult: "loss", totalResult: null }),
    finalGame({ gameId: 3, spreadResult: "push", totalResult: "win" }),
  ];
  assert.deepEqual(weekRecord(games), {
    spread: { win: 1, loss: 1, push: 1 },
    total: { win: 1, loss: 1, push: 0 },
  });
});

test("topResults ranks graded leans of one outcome by edge", () => {
  const games = [
    finalGame({ gameId: 1, spreadResult: "win", edgeSpread: 3, totalResult: "loss", edgeTotal: 9 }),
    finalGame({ gameId: 2, spreadResult: "win", edgeSpread: 7, totalResult: "win", edgeTotal: 2 }),
  ];
  const wins = topResults(games, "win", 5);
  assert.deepEqual(wins.map((w) => [w.game.gameId, w.kind]), [[2, "spread"], [1, "spread"], [2, "total"]]);
  const losses = topResults(games, "loss", 5);
  assert.deepEqual(losses.map((w) => [w.game.gameId, w.kind]), [[1, "total"]]);
});

test("result filters and sorts", () => {
  const win = finalGame({ gameId: 1, spreadResult: "win", totalLean: null });
  const loss = finalGame({ gameId: 2, spreadResult: "loss", spreadLean: "away", totalLean: null });
  const none = finalGame({ gameId: 3, spreadLean: null, totalLean: null });
  assert.equal(matchesResult(win, "win"), true);
  assert.equal(matchesResult(win, "loss"), false);
  assert.equal(matchesResult(none, "none"), true);
  assert.equal(matchesResult(win, "all"), true);
  // win covers +3.5, loss misses -3.5, none has no cover.
  assert.deepEqual(sortResults([loss, none, win], "bestResult").map((g) => g.gameId), [1, 2, 3]);
  assert.deepEqual(sortResults([win, none, loss], "worstResult").map((g) => g.gameId), [2, 1, 3]);
});


import { breakEvenDelta, finalMarginText } from "./picks-proto.ts";

test("leans explain their direction in plain language", () => {
  const fav = leanFor(game({}), "spread");
  assert.equal(fav?.explain, "Home to win by more than 3.5");
  assert.equal(fav?.model, "Home by 6.5");
  assert.equal(fav?.dir, "home");
  assert.equal(fav?.team, "Home");

  const dog = leanFor(game({ spreadLean: "away", homeTeamSpreadLine: -3.5 }), "spread");
  assert.equal(dog?.explain, "Away to win, or lose by fewer than 3.5");
  assert.equal(dog?.model, "Away loses by 6.5");

  const pk = leanFor(game({ homeTeamSpreadLine: 0 }), "spread");
  assert.equal(pk?.explain, "Home to win");

  const over = leanFor(game({}), "total");
  assert.equal(over?.explain, "Combined score above 50.5");
  assert.equal(over?.model, "total 55.0");
  assert.equal(leanFor(game({ totalLean: "under" }), "total")?.explain, "Combined score below 50.5");
});

test("breakEvenDelta is signed, bounded and comparable", () => {
  const below = breakEvenDelta(93, 103);
  assert.equal(Math.round((below.delta ?? 0) * 10) / 10, -5);
  assert.ok(below.fill < 0 && below.fill > -1);
  assert.equal(below.decided, 196);
  assert.ok(breakEvenDelta(82, 77).fill > -0.1);
  assert.equal(breakEvenDelta(0, 0).rate, null);
  assert.equal(breakEvenDelta(0, 0).fill, 0);
  assert.equal(breakEvenDelta(20, 0).fill, 1);
  assert.equal(breakEvenDelta(0, 20).fill, -1);
});

test("finalMarginText reads the result from the leaned team's side", () => {
  const g = game({ homePoints: 24, awayPoints: 17 });
  assert.equal(finalMarginText(g, "Home"), "Home won by 7");
  assert.equal(finalMarginText(g, "Away"), "Away lost by 7");
  assert.equal(finalMarginText(game({}), "Home"), null);
});
