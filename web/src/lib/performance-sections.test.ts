import test from "node:test";
import assert from "node:assert/strict";
import { loadPerformanceSections } from "./performance-sections.ts";

test("a failing prospective loader leaves the replay section available", async () => {
  const errors: string[] = [];
  const result = await loadPerformanceSections(
    async () => "replay-data",
    async () => {
      throw new Error("prospective receipt URI is not recognised");
    },
    (section) => errors.push(section),
  );

  assert.deepEqual(result.replay, { status: "ok", value: "replay-data" });
  assert.deepEqual(result.prospective, { status: "unavailable" });
  assert.deepEqual(errors, ["prospective"]);
});

test("a failing replay loader leaves the prospective section available", async () => {
  const result = await loadPerformanceSections(
    async () => {
      throw new Error("replay query failed");
    },
    async () => "prospective-data",
  );

  assert.deepEqual(result.replay, { status: "unavailable" });
  assert.deepEqual(result.prospective, { status: "ok", value: "prospective-data" });
});

test("both sections load when neither loader fails", async () => {
  const result = await loadPerformanceSections(
    async () => 1,
    async () => 2,
  );
  assert.deepEqual(result, {
    replay: { status: "ok", value: 1 },
    prospective: { status: "ok", value: 2 },
  });
});
