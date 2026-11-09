import test from "node:test";
import assert from "node:assert/strict";
import { breakEvenBand, breakEvenCaveat, weeklyAndCumulative, type TrendGame } from "./performance-trend.ts";

const games: TrendGame[] = [
  { week: 0, spreadResult: "win", totalResult: "loss" },
  { week: 0, spreadResult: "win", totalResult: "push" },
  { week: 1, spreadResult: "push", totalResult: "win" },
  { week: 1, spreadResult: "push", totalResult: "win" },
  { week: 2, spreadResult: "loss", totalResult: null },
];

const close = (actual: number | null, expected: number) => {
  assert.notEqual(actual, null);
  assert.ok(Math.abs((actual as number) - expected) < 1e-9);
};

test("a push-only week has no rate yet carries the season-to-date record", () => {
  const rows = weeklyAndCumulative(games, [0, 1, 2]);
  assert.deepEqual(rows.map((row) => row.week), [0, 1, 2]);
  assert.equal(rows[1].weekly.spread.winRate, null);
  assert.deepEqual(
    [rows[1].cumulative.spread.win, rows[1].cumulative.spread.loss, rows[1].cumulative.spread.push],
    [2, 0, 2],
  );
  assert.equal(rows[1].cumulative.spread.winRate, 100);
});

test("cumulative records add each week to everything before it", () => {
  const rows = weeklyAndCumulative(games, [0, 1, 2]);
  close(rows[2].cumulative.spread.winRate, 200 / 3);
  // Totals: 2-1-1 through week 1, unchanged by a week with no total grade.
  assert.deepEqual(
    [rows[2].cumulative.total.win, rows[2].cumulative.total.loss, rows[2].cumulative.total.push],
    [2, 1, 1],
  );
  assert.equal(rows[2].weekly.total.winRate, null);
  // Combined through week 2: spread 2-1-2 plus totals 2-1-1.
  assert.deepEqual(
    [rows[2].cumulative.combined.win, rows[2].cumulative.combined.loss, rows[2].cumulative.combined.push],
    [4, 2, 3],
  );
  assert.equal(rows[0].weekly.total.winRate, 0);
});

test("no weeks and no games give no rows and no rates", () => {
  assert.deepEqual(weeklyAndCumulative([], []), []);
  assert.equal(weeklyAndCumulative([], [0])[0].cumulative.combined.winRate, null);
});

test("the break-even band narrows with sample size", () => {
  const band = breakEvenBand(559)!;
  assert.ok(Math.abs(band.low - 48.26) < 0.01, String(band.low));
  assert.ok(Math.abs(band.high - 56.54) < 0.01, String(band.high));
  assert.equal(breakEvenBand(0), null);
  assert.equal(breakEvenBand(-3), null);
  const small = breakEvenBand(50)!;
  assert.ok(small.high - small.low > band.high - band.low);
});

test("the caveat names luck inside the band and the outside range beyond it", () => {
  assert.match(breakEvenCaveat(50, 559)!, /within normal luck of break-even/);
  assert.match(breakEvenCaveat(60, 559)!, /outside that range/);
  assert.equal(breakEvenCaveat(null, 559), null);
  assert.equal(breakEvenCaveat(55, 0), null);
});
