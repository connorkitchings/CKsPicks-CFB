import assert from "node:assert/strict";
import test from "node:test";
import { parseGameId } from "./matchup-id.ts";

test("accepts positive integer segments", () => {
  assert.equal(parseGameId("1"), 1);
  assert.equal(parseGameId("401752800"), 401752800);
});

test("rejects zero, negatives, decimals, exponents, text and empty", () => {
  for (const s of ["0", "-1", "1.5", "1e3", "abc", "", " 1", "0x10"]) assert.equal(parseGameId(s), null, s);
});

test("rejects ids beyond 32-bit range", () => {
  assert.equal(parseGameId("2147483648"), null);
  assert.equal(parseGameId("99999999999999999999"), null);
});
