import assert from "node:assert/strict";
import test from "node:test";
import {
  closerSide,
  pairedErrors,
  parseTarget,
  scatterDomain,
  sortPairedErrors,
  type PairedError,
} from "./performance-errors.ts";
import { comparableGames, type MarketGame } from "./performance-market.ts";

const PRE = "model_side_best_quote_v2:retained_prekickoff";
const RETRO = "model_side_best_quote_v2:cfbd_retrospective";

function game(over: Partial<MarketGame>): MarketGame {
  return {
    gameId: 1, week: 1, homeTeam: "Home", awayTeam: "Away", homePoints: 30, awayPoints: 20,
    predictedSpread: 7, predictedTotal: 55, spreadResult: "win", totalResult: "win",
    canonicalSpread: -3, canonicalTotal: 48, spreadGradingVersion: PRE, totalGradingVersion: PRE, ...over,
  };
}

test("eligibility is exactly the existing comparison set, pushes included", () => {
  const games = [
    game({ gameId: 1 }),
    game({ gameId: 2, spreadResult: "push", totalResult: "push" }),
    game({ gameId: 3, spreadResult: null }),
    game({ gameId: 4, predictedSpread: null }),
    game({ gameId: 5, canonicalSpread: null }),
    game({ gameId: 6, homePoints: null }),
    game({ gameId: 7, spreadGradingVersion: RETRO }),
    game({ gameId: 8, spreadGradingVersion: null }),
  ];
  for (const target of ["spread", "total"] as const) {
    assert.deepEqual(pairedErrors(games, target), comparableGames(games, target));
  }
  assert.deepEqual(pairedErrors(games, "spread").map((p) => p.gameId), [1, 2]);
});

test("a game missing one target stays eligible for the other", () => {
  const games = [game({ predictedTotal: null, canonicalTotal: null, totalResult: null })];
  assert.equal(pairedErrors(games, "total").length, 0);
  assert.equal(pairedErrors(games, "spread").length, 1);
});

test("sign conventions: errors are prediction minus actual and the line is the implied value", () => {
  const [spread] = pairedErrors([game({})], "spread");
  assert.equal(spread.actual, 10);
  assert.equal(spread.line, 3);
  assert.equal(spread.modelError, -3);
  assert.equal(spread.lineError, -7);
  const [total] = pairedErrors([game({})], "total");
  assert.equal(total.actual, 50);
  assert.equal(total.modelError, 5);
  assert.equal(total.lineError, -2);
});

function pair(modelError: number, lineError: number, gameId = 1): PairedError {
  return { gameId, week: 1, homeTeam: "H", awayTeam: "A", actual: 0, model: modelError, line: lineError, modelError, lineError };
}

test("equal-error diagonal: below is model closer, above is market closer, on it is even", () => {
  assert.equal(closerSide(pair(1, 3)), "model");
  assert.equal(closerSide(pair(-3, 1)), "market");
  assert.equal(closerSide(pair(2, -2)), "even");
  assert.equal(closerSide(pair(0, 0)), "even");
});

test("scatterDomain is one shared square bound that covers both axes", () => {
  assert.equal(scatterDomain([]), 1);
  assert.equal(scatterDomain([pair(0.4, -0.2)]), 1);
  assert.equal(scatterDomain([pair(3, -12)]), 15);
  assert.equal(scatterDomain([pair(-35, 8)]), 35);
  assert.equal(scatterDomain([pair(-41, 8)]), 50);
  assert.equal(scatterDomain([pair(45, 1)]), 50);
});

test("parseTarget normalizes invalid and repeated values to the spread", () => {
  assert.equal(parseTarget("total"), "total");
  assert.equal(parseTarget("spread"), "spread");
  for (const bad of [undefined, null, "", "TOTAL", "ats", ["total", "spread"]]) assert.equal(parseTarget(bad), "spread");
});

test("sorting works both ways, on absolute errors, and ties break on game id", () => {
  const rows = [pair(-5, 1, 3), pair(2, 9, 1), pair(5, 1, 2)];
  assert.deepEqual(sortPairedErrors(rows, "modelError", "desc").map((p) => p.gameId), [2, 3, 1]);
  assert.deepEqual(sortPairedErrors(rows, "modelError", "asc").map((p) => p.gameId), [1, 2, 3]);
  assert.deepEqual(sortPairedErrors(rows, "closer", "asc").map((p) => p.gameId), [1, 2, 3]);
  assert.deepEqual(sortPairedErrors(rows, "game", "asc").map((p) => p.gameId), [1, 2, 3]);
  assert.deepEqual(rows.map((p) => p.gameId), [3, 1, 2], "input is not mutated");
});
