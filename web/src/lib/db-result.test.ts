import assert from "node:assert/strict";
import test from "node:test";
import { existsFrom, rowsOf } from "./db-result.ts";

test("existsFrom reads both the Neon HTTP object shape and a bare array", () => {
  assert.equal(existsFrom({ rows: [{ exists: true }], fields: [] }), true);
  assert.equal(existsFrom([{ exists: true }]), true);
  assert.equal(existsFrom({ rows: [{ exists: false }] }), false);
  assert.equal(existsFrom({ rows: [] }), false);
  assert.equal(existsFrom([]), false);
});

test("rowsOf tolerates null, undefined and unexpected shapes", () => {
  assert.deepEqual(rowsOf(null), []);
  assert.deepEqual(rowsOf(undefined), []);
  assert.deepEqual(rowsOf({ rows: "nope" }), []);
  assert.deepEqual(rowsOf({ rows: [{ a: 1 }] }), [{ a: 1 }]);
});
