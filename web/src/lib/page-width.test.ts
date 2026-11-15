import assert from "node:assert/strict";
import test from "node:test";
import { PAGE_WIDTHS, pageWidthFor } from "./page-width.ts";

test("page widths map to the shared container classes", () => {
  assert.deepEqual(PAGE_WIDTHS, { slate: "max-w-[1200px]", wide: "max-w-[1200px]", narrow: "max-w-[760px]" });
});

test("slate routes use the slate width", () => {
  for (const p of ["/", "/teams", "/stats", "/stats/x", "/teams/Ohio%20State"]) {
    assert.equal(pageWidthFor(p), "slate", p);
  }
});

test("ratings, model and matchup routes use the wide width", () => {
  for (const p of ["/ratings", "/model", "/model/method", "/matchup/123"]) {
    assert.equal(pageWidthFor(p), "wide", p);
  }
});

test("other routes use the narrow width", () => {
  for (const p of ["/nope"]) {
    assert.equal(pageWidthFor(p), "narrow", p);
  }
});
