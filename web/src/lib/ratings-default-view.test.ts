import assert from "node:assert/strict";
import test from "node:test";
import { isDefaultView } from "./ratings-default-view.ts";

const base = { conference: "all", sort: "overall", period: "latest", defaultPeriod: "latest" };

test("the default period is the default view whatever its position in the timeline", () => {
  assert.equal(isDefaultView(base), true);
});

test("an older period, a conference, or another sort is a filtered view", () => {
  assert.equal(isDefaultView({ ...base, period: "preseason" }), false);
  assert.equal(isDefaultView({ ...base, conference: "sec" }), false);
  assert.equal(isDefaultView({ ...base, sort: "offense" }), false);
});
