import assert from "node:assert/strict";
import test from "node:test";
import { splitPerformanceByWeek, type PerformanceRow } from "./performance-split.ts";

const row = (week: number, evidenceClass: PerformanceRow["evidenceClass"], spreadResult: PerformanceRow["spreadResult"]) => ({
  week, evidenceClass, spreadResult, totalResult: null,
  predictedMargin: 3, predictedTotal: 50, marginStdDev: 10, totalStdDev: 12, homePoints: 24, awayPoints: 21,
});

test("one set of rows splits into season-to-date before the week and the week itself", () => {
  const rows = [row(1, "replay", "win"), row(2, "live", "loss"), row(3, "live", "win"), row(4, "live", "win")];
  const split = splitPerformanceByWeek(rows, 3);
  const [beforeAll, beforeReplay, beforeLive] = split.before;
  assert.deepEqual([beforeAll.games, beforeAll.spread], [2, { win: 1, loss: 1, push: 0 }]);
  assert.equal(beforeReplay.games, 1);
  assert.equal(beforeLive.games, 1);
  const [weekAll] = split.week;
  assert.deepEqual([weekAll.games, weekAll.spread], [1, { win: 1, loss: 0, push: 0 }]);
});

test("a week with no rows summarizes to empty records, and later weeks are ignored", () => {
  const split = splitPerformanceByWeek([row(5, "live", "win")], 3);
  assert.equal(split.before[0].games, 0);
  assert.equal(split.week[0].games, 0);
  assert.equal(split.week[0].marginMae, null);
});
