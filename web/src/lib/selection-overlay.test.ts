import assert from "node:assert/strict";
import test from "node:test";

import { overlaySelection } from "./selection-overlay.ts";

const base = {
  homeTeamSpreadLine: -3.5,
  predictedSpread: 1.0,
  spreadLean: "away" as "home" | "away" | null,
  edgeSpread: 2.1 as number | null,
  totalLine: 50,
  predictedTotal: 48,
  totalLean: "under" as "over" | "under" | null,
  edgeTotal: 1.4 as number | null,
};

const selection = {
  spread: { point: -3, side: "away", edge: 2.4, source: "book" },
  total: { point: 49.5, side: "under", edge: 1.9, source: "book" },
};

test("selection supplies line, side, edge and source when the prediction has a lean", () => {
  const out = overlaySelection(base, selection);
  assert.equal(out.homeTeamSpreadLine, -3);
  assert.equal(out.spreadLean, "away");
  assert.equal(out.edgeSpread, 2.4);
  assert.equal(out.totalLine, 49.5);
  assert.equal(out.totalLean, "under");
  assert.equal(out.edgeTotal, 1.9);
  assert.equal(out.spreadSource, "book");
});

test("a null-lean prediction gets the model-vs-line lean, not the publisher's default side", () => {
  const nullLean = { ...base, spreadLean: null, edgeSpread: null, totalLean: null, edgeTotal: null };
  // model home margin 1.0 vs home line -3.5 => away by 2.5; total 48 vs 50 => under by 2.
  const defaulted = {
    spread: { point: -3.5, side: "home", edge: 0, source: "book" },
    total: { point: 50, side: "over", edge: 0, source: "book" },
  };
  const out = overlaySelection(nullLean, defaulted);
  assert.equal(out.spreadLean, "away");
  assert.equal(out.edgeSpread, 2.5);
  assert.equal(out.totalLean, "under");
  assert.equal(out.edgeTotal, 2);
  assert.equal(out.homeTeamSpreadLine, -3.5);
  assert.equal(out.totalLine, 50);
});

test("the derived lean uses the selected quote's line", () => {
  const nullLean = { ...base, predictedSpread: 3.6, spreadLean: null, edgeSpread: null };
  // vs -3.5 the model is home by 0.1; vs the selected -4 it is away by 0.4.
  const out = overlaySelection(nullLean, {
    spread: { point: -4, side: "home", edge: 0, source: "book" },
  });
  assert.equal(out.spreadLean, "away");
  assert.equal(Math.round((out.edgeSpread ?? 0) * 10) / 10, 0.4);
});

// Coupled to the grade backfill's tie rule (`>`: a tie is away/under) and to D7a in
// docs/data/known_issues.md. If D7a changes the tie rule, change deriveSpreadView /
// deriveTotalView and this test together so the card and the grade keep agreeing.
test("an exact tie follows the grader: away / under", () => {
  const nullLean = {
    ...base,
    predictedSpread: 3.5,
    spreadLean: null,
    edgeSpread: null,
    predictedTotal: 50,
    totalLean: null,
    edgeTotal: null,
  };
  const out = overlaySelection(nullLean, undefined);
  assert.equal(out.spreadLean, "away");
  assert.equal(out.totalLean, "under");
  assert.equal(out.edgeSpread, 0);
});

test("a null-lean row without a prediction or line stays without a lean", () => {
  const out = overlaySelection(
    { ...base, predictedSpread: null, homeTeamSpreadLine: null, spreadLean: null, edgeSpread: null },
    undefined,
  );
  assert.equal(out.spreadLean, null);
  assert.equal(out.edgeSpread, null);
});

test("only the null target is derived", () => {
  const out = overlaySelection(
    { ...base, totalLean: null, edgeTotal: null, predictedTotal: 55 },
    { ...selection, total: { point: 49.5, side: "under", edge: 0, source: "book" } },
  );
  assert.equal(out.spreadLean, "away");
  assert.equal(out.totalLean, "over");
});

test("no selection keeps the prediction row", () => {
  const out = overlaySelection(base, undefined);
  assert.equal(out.spreadLean, "away");
  assert.equal(out.homeTeamSpreadLine, -3.5);
  assert.equal(out.spreadSource, null);
});
