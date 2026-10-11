import test from "node:test";
import assert from "node:assert/strict";
import { loadPerformanceRecord } from "./performance-sections.ts";

test("the cumulative loader returns the selected record", async () => {
  assert.deepEqual(await loadPerformanceRecord(async () => ({ spread: 128, total: 137 })),
    { status: "ok", value: { spread: 128, total: 137 } });
});

test("a query failure hides the cumulative record and reports the error", async () => {
  const failure = new Error("query failed");
  const errors: unknown[] = [];
  const result = await loadPerformanceRecord(async () => { throw failure; }, error => errors.push(error));
  assert.deepEqual(result, { status: "unavailable" });
  assert.deepEqual(errors, [failure]);
});


test("cumulative queries include selected pending grades and do not require a freeze designation", async () => {
  const { readFileSync } = await import("node:fs");
  const source = readFileSync(new URL("./v5.ts", import.meta.url), "utf8");
  const query = source.slice(source.indexOf("export const getV5PerformanceDetail"));
  assert.match(query, /from\(schema.siteWeekSelections\)/);
  assert.match(query, /inArray\(schema.predictionRuns.evidenceClass, \[\.\.\.V5_RECORD_EVIDENCE\]\)/);
  assert.doesNotMatch(query, /prospectiveWeekRecords/);
  const stats = readFileSync(new URL("./queries.ts", import.meta.url), "utf8")
    .split("export const getSystemStatsThroughWeek")[1];
  assert.doesNotMatch(stats, /eq\(schema.predictionRuns.state, "scored"\)/);
});
