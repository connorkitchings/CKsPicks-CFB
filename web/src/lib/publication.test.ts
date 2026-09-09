import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { parsePublicationMode } from "./publication.ts";

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
