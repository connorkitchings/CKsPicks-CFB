import assert from "node:assert/strict";
import test from "node:test";
import { PAGE_WIDTHS, pageWidthFor } from "./page-width.ts";

test("page widths map to the shared container classes", () => {
  assert.deepEqual(PAGE_WIDTHS, { slate: "max-w-6xl", wide: "max-w-5xl", narrow: "max-w-4xl" });
});

test("slate routes use the slate width", () => {
  for (const p of ["/", "/results", "/results/anything", "/charts", "/charts/x"]) {
    assert.equal(pageWidthFor(p), "slate", p);
  }
});

test("matchup, ratings and performance routes use the wide width", () => {
  for (const p of ["/matchup", "/matchup/123", "/ratings", "/performance"]) {
    assert.equal(pageWidthFor(p), "wide", p);
  }
});

test("other routes use the narrow width", () => {
  for (const p of ["/methodology", "/teams/Ohio%20State", "/nope"]) {
    assert.equal(pageWidthFor(p), "narrow", p);
  }
});
