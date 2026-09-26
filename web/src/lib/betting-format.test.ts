import assert from "node:assert/strict";
import test from "node:test";

import {
  signedSpread,
  marketSpreadView,
  modelSpreadView,
  spreadLabel,
  spreadEdge,
  totalEdge,
  spreadBetLabel,
  totalBetLabel,
} from "./betting-format.ts";

const HOME = "Georgia";
const AWAY = "Alabama";

test("signedSpread prefixes positives and leaves negatives bare", () => {
  assert.equal(signedSpread(3.5), "+3.5");
  assert.equal(signedSpread(-3.5), "-3.5");
  assert.equal(signedSpread(0), "0.0");
});

test("market view favors the home team on a negative line", () => {
  assert.deepEqual(marketSpreadView(HOME, AWAY, -7), { team: HOME, line: -7 });
});

test("market view flips to the away team on a positive line", () => {
  assert.deepEqual(marketSpreadView(HOME, AWAY, 3.5), { team: AWAY, line: -3.5 });
});

test("market view handles pick'em and missing lines", () => {
  assert.equal(marketSpreadView(HOME, AWAY, 0), "PK");
  assert.equal(marketSpreadView(HOME, AWAY, null), null);
});

test("model view converts a home margin into a negative home line", () => {
  assert.deepEqual(modelSpreadView(HOME, AWAY, 10), { team: HOME, line: -10 });
});

test("model view converts an away margin into a negative away line", () => {
  assert.deepEqual(modelSpreadView(HOME, AWAY, -4.5), { team: AWAY, line: -4.5 });
});

test("model view handles pick'em and missing predictions", () => {
  assert.equal(modelSpreadView(HOME, AWAY, 0), "PK");
  assert.equal(modelSpreadView(HOME, AWAY, null), null);
});

test("spreadLabel renders views, placeholders, and pick'em", () => {
  assert.equal(spreadLabel({ team: HOME, line: -7 }), "Georgia -7.0");
  assert.equal(spreadLabel({ team: AWAY, line: -3.5 }), "Alabama -3.5");
  assert.equal(spreadLabel(null), "—");
  assert.equal(spreadLabel("PK"), "PK");
});

test("spreadEdge is model minus market and null-safe", () => {
  // Model higher on Georgia than the market: -10 vs -7.
  assert.equal(
    spreadEdge(
      modelSpreadView(HOME, AWAY, 10),
      marketSpreadView(HOME, AWAY, -7),
    ),
    -3,
  );
  assert.equal(spreadEdge(null, marketSpreadView(HOME, AWAY, -7)), null);
  assert.equal(spreadEdge("PK", marketSpreadView(HOME, AWAY, -7)), null);
  assert.equal(spreadEdge(modelSpreadView(HOME, AWAY, 10), "PK"), null);
});

test("totalEdge is predicted minus market and null-safe", () => {
  assert.equal(totalEdge(52.5, 48), 4.5);
  assert.equal(totalEdge(41, 48), -7);
  assert.equal(totalEdge(null, 48), null);
  assert.equal(totalEdge(52.5, null), null);
});

test("spread bet takes the home line as-is but flips it for the away side", () => {
  // Home -7: backing Georgia means laying -7.0.
  assert.equal(spreadBetLabel(HOME, AWAY, "home", -7), "Georgia -7.0");
  // Same line, backing Alabama means getting +7.0.
  assert.equal(spreadBetLabel(HOME, AWAY, "away", -7), "Alabama +7.0");
  // Home dog +3.5: backing Georgia means getting +3.5.
  assert.equal(spreadBetLabel(HOME, AWAY, "home", 3.5), "Georgia +3.5");
  assert.equal(spreadBetLabel(HOME, AWAY, null, -7), null);
  assert.equal(spreadBetLabel(HOME, AWAY, "home", null), null);
});

test("total bet labels direction and line", () => {
  assert.equal(totalBetLabel("over", 48), "↑ Over 48.0");
  assert.equal(totalBetLabel("under", 48), "↓ Under 48.0");
  assert.equal(totalBetLabel(null, 48), null);
  assert.equal(totalBetLabel("over", null), null);
});
