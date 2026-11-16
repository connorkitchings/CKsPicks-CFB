import assert from "node:assert/strict";
import test from "node:test";
import { statsWindowLabel } from "./stats-window.ts";

test("statsWindowLabel never prints a negative or zeroth completed week", () => {
  assert.equal(statsWindowLabel(0), "Preseason statistics");
  assert.equal(statsWindowLabel(1), "Statistics before Week 1");
  assert.equal(statsWindowLabel(2), "Statistics through Week 1");
  assert.equal(statsWindowLabel(12), "Statistics through Week 11");
});
