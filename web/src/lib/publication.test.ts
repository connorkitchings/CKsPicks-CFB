import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { parsePublicationMode, displaySystemName, deriveSpreadView, deriveTotalView } from "./publication.ts";

test("publication mode defaults to market-only", () => {
  assert.equal(parsePublicationMode(undefined), "market");
  assert.equal(parsePublicationMode(""), "market");
  assert.equal(parsePublicationMode("true"), "market");
  assert.equal(parsePublicationMode("PREDICTIONS"), "market");
});

test("prediction output requires the exact opt-in value", () => {
  assert.equal(parsePublicationMode("predictions"), "predictions");
});

test("market query projects settled grades but excludes model-only columns", () => {
  const source = readFileSync(new URL("./queries.ts", import.meta.url), "utf8");
  const marketQueryStart = source.indexOf("export async function getMarketGamesForWeek");
  const marketQueryEnd = source.indexOf("function emptyStats", marketQueryStart);
  assert.notEqual(marketQueryStart, -1, "market query must exist");
  assert.notEqual(marketQueryEnd, -1, "market query boundary must exist");
  const marketQuery = source.slice(marketQueryStart, marketQueryEnd);
  assert.match(marketQuery, /homeTeamSpreadLine: schema\.games\.homeTeamSpreadLine/);
  assert.match(marketQuery, /totalLine: schema\.games\.totalLine/);
  assert.match(marketQuery, /spreadResult/);
  assert.match(marketQuery, /totalResult/);
  assert.doesNotMatch(
    marketQuery,
    /predictedSpread|predictedTotal|spreadLean|totalLean|edgeSpread|edgeTotal|highConfidence|modelId|systemName/,
  );
});

test("V5 displays as Blitzkrieg without touching other system names", () => {
  assert.equal(displaySystemName("Trench Warfare V5"), "Blitzkrieg");
  assert.equal(displaySystemName("Trench Warfare V4"), "Trench Warfare V4");
  assert.equal(displaySystemName("week0-2026-v4-strict-20260818-r2"), "week0-2026-v4-strict-20260818-r2");
  assert.equal(displaySystemName(null), null);
});

test("spread lean follows home-margin versus the line", () => {
  assert.deepEqual(deriveSpreadView(10, -7), { lean: "home", edge: 3 });
  assert.deepEqual(deriveSpreadView(-10, -7), { lean: "away", edge: 17 });
  assert.deepEqual(deriveSpreadView(7, -7), { lean: "away", edge: 0 });
  assert.deepEqual(deriveSpreadView(null, -7), { lean: null, edge: null });
  assert.deepEqual(deriveSpreadView(3.5, null), { lean: null, edge: null });
});

test("total lean follows predicted total versus the line", () => {
  assert.deepEqual(deriveTotalView(52, 48.5), { lean: "over", edge: 3.5 });
  assert.deepEqual(deriveTotalView(40, 48.5), { lean: "under", edge: 8.5 });
  assert.deepEqual(deriveTotalView(48.5, 48.5), { lean: "under", edge: 0 });
  assert.deepEqual(deriveTotalView(null, 48.5), { lean: null, edge: null });
  assert.deepEqual(deriveTotalView(52, null), { lean: null, edge: null });
});
