import test from "node:test";
import assert from "node:assert/strict";
import {
  BIG_MISS_POINTS,
  comparableGames,
  lineSourceCounts,
  lineSourceOf,
  marketComparison,
  type MarketGame,
} from "./performance-market.ts";

const PRE = "model_side_best_quote_v2:retained_prekickoff";
const RETRO = "model_side_best_quote_v2:cfbd_retrospective";

const close = (actual: number | null, expected: number) => {
  assert.notEqual(actual, null);
  assert.ok(Math.abs((actual as number) - expected) < 1e-9, `${actual} !== ${expected}`);
};

function game(over: Partial<MarketGame> & { gameId: number }): MarketGame {
  return {
    week: 1,
    homeTeam: `Home ${over.gameId}`,
    awayTeam: `Away ${over.gameId}`,
    homePoints: 0,
    awayPoints: 0,
    predictedSpread: null,
    predictedTotal: null,
    spreadResult: null,
    totalResult: null,
    canonicalSpread: null,
    canonicalTotal: null,
    spreadGradingVersion: PRE,
    totalGradingVersion: PRE,
    ...over,
  };
}

/*
 * Spread (actual = home - away; line-implied home margin = -canonicalSpread):
 *   id actual forecast canon  line  modelErr lineErr
 *   1  +10    +14      -7     +7     +4       -3     line closer
 *   2  -7     +3       +3     -3     +10      +4     line closer (a push)
 *   3  +14    +12      -10    +10    -2       -4     model closer
 *   4  -3     -3       0      0      0        +3     model closer (pick'em)
 *   5  +6     +9       -3     +3     +3       -3     exact tie
 *   6  +42    +10      -14    +14    -32      -28    line closer, model big miss
 * Totals (actual = home + away):
 *   id actual forecast line modelErr lineErr
 *   1  50     55       48   +5       -2
 *   2  41     45       44   +4       +3
 *   3  42     42       46   0        +4
 *   4  45     50       50   +5       +5     exact tie
 *   5  56     50       52   -6       -4
 *   6  48     80       76   +32      +28
 */
const games: MarketGame[] = [
  game({ gameId: 1, week: 1, homePoints: 30, awayPoints: 20, predictedSpread: 14, canonicalSpread: -7, spreadResult: "win", predictedTotal: 55, canonicalTotal: 48, totalResult: "win" }),
  game({ gameId: 2, week: 1, homePoints: 17, awayPoints: 24, predictedSpread: 3, canonicalSpread: 3, spreadResult: "push", predictedTotal: 45, canonicalTotal: 44, totalResult: "push" }),
  game({ gameId: 3, week: 1, homePoints: 28, awayPoints: 14, predictedSpread: 12, canonicalSpread: -10, spreadResult: "loss", predictedTotal: 42, canonicalTotal: 46, totalResult: "loss" }),
  game({ gameId: 4, week: 2, homePoints: 21, awayPoints: 24, predictedSpread: -3, canonicalSpread: 0, spreadResult: "win", predictedTotal: 50, canonicalTotal: 50, totalResult: "win" }),
  game({ gameId: 5, week: 2, homePoints: 31, awayPoints: 25, predictedSpread: 9, canonicalSpread: -3, spreadResult: "win", predictedTotal: 50, canonicalTotal: 52, totalResult: "win" }),
  game({ gameId: 6, week: 2, homePoints: 45, awayPoints: 3, predictedSpread: 10, canonicalSpread: -14, spreadResult: "loss", predictedTotal: 80, canonicalTotal: 76, totalResult: "loss" }),
  // Ungraded: no final score and no result.
  game({ gameId: 7, week: 2, predictedSpread: 4, canonicalSpread: -3, predictedTotal: 50, canonicalTotal: 51 }),
  // Graded at the retrospective line: excluded and counted.
  game({ gameId: 8, week: 2, homePoints: 40, awayPoints: 10, predictedSpread: 3, canonicalSpread: -1, spreadResult: "win", spreadGradingVersion: RETRO, predictedTotal: 50, canonicalTotal: 49, totalResult: "win", totalGradingVersion: RETRO }),
  // Unreadable grading versions fail closed.
  game({ gameId: 9, week: 2, homePoints: 20, awayPoints: 10, predictedSpread: 3, canonicalSpread: -1, spreadResult: "win", spreadGradingVersion: "model_side_best_quote_v9:retained_prekickoff", predictedTotal: 50, canonicalTotal: 49, totalResult: "win", totalGradingVersion: null }),
];

test("lineSourceOf names both real suffixes and fails closed otherwise", () => {
  assert.equal(lineSourceOf(PRE), "prekickoff");
  assert.equal(lineSourceOf(RETRO), "retrospective");
  assert.equal(lineSourceOf(null), "unknown");
  assert.equal(lineSourceOf(undefined), "unknown");
  assert.equal(lineSourceOf(""), "unknown");
  assert.equal(lineSourceOf("model_side_best_quote_v3:retained_prekickoff"), "unknown");
  assert.equal(lineSourceOf("model_side_best_quote_v2:something_new"), "unknown");
});

test("the spread comparison uses the retained pre-kickoff line on graded, final games only", () => {
  assert.deepEqual(comparableGames(games, "spread").map((row) => row.gameId), [1, 2, 3, 4, 5, 6]);
  const result = marketComparison(games, "spread")!;
  assert.equal(result.n, 6);
  close(result.modelMiss, 51 / 6);
  close(result.lineMiss, 45 / 6);
  close(result.modelLean, -17 / 6);
  close(result.lineLean, -31 / 6);
  assert.equal(result.modelCloser, 2);
  assert.equal(result.lineCloser, 3);
  assert.equal(result.even, 1);
  assert.equal(result.decided, 5);
});

test("the totals comparison mirrors the spread rules on combined points", () => {
  const result = marketComparison(games, "total")!;
  assert.equal(result.n, 6);
  close(result.modelMiss, 52 / 6);
  close(result.lineMiss, 46 / 6);
  close(result.modelLean, 40 / 6);
  close(result.lineLean, 34 / 6);
  assert.equal(result.modelCloser, 1);
  assert.equal(result.lineCloser, 4);
  assert.equal(result.even, 1);
  assert.equal(result.decided, 5);
});

test("a pick'em line implies a zero margin, never negative zero", () => {
  const pickem = comparableGames(games, "spread").find((row) => row.gameId === 4)!;
  assert.ok(Object.is(pickem.line, 0));
  assert.equal(pickem.lineError, 3);
  const negativeZero = comparableGames([game({ gameId: 10, homePoints: 7, awayPoints: 7, predictedSpread: 0, canonicalSpread: -0, spreadResult: "push" })], "spread");
  assert.ok(Object.is(negativeZero[0].line, 0));
});

test("big misses are strictly above the threshold", () => {
  assert.equal(BIG_MISS_POINTS, 28);
  const spread = marketComparison(games, "spread")!;
  // Model miss of 32 counts; the line's miss of exactly 28 does not.
  assert.equal(spread.modelBigMisses, 1);
  assert.equal(spread.lineBigMisses, 0);
  const lower = marketComparison(games, "spread", 21)!;
  assert.equal(lower.modelBigMisses, 1);
  assert.equal(lower.lineBigMisses, 1);
});

test("retrospective and unknown lines are excluded and counted, ungraded games ignored", () => {
  assert.deepEqual(lineSourceCounts(games, "spread"), { prekickoff: 6, retrospective: 1, unknown: 1 });
  assert.deepEqual(lineSourceCounts(games, "total"), { prekickoff: 6, retrospective: 1, unknown: 1 });
});

test("empty input and a comparison set of zero give null, never NaN", () => {
  assert.equal(marketComparison([], "spread"), null);
  assert.equal(marketComparison(games.filter((g) => g.gameId >= 7), "total"), null);
  assert.deepEqual(lineSourceCounts([], "total"), { prekickoff: 0, retrospective: 0, unknown: 0 });
});

