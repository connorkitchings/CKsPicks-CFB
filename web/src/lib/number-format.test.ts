import assert from "node:assert/strict";
import test from "node:test";
import { signedFixed } from "./number-format.ts";

test("signedFixed drops the sign when the value rounds to zero", () => {
  assert.equal(signedFixed(-0.001), "0.00");
  assert.equal(signedFixed(0), "0.00");
  assert.equal(signedFixed(0.004), "0.00");
  assert.equal(signedFixed(-0.04, 1), "0.0");
  assert.equal(signedFixed(-0.2, 0), "0");
});

test("signedFixed signs positives and keeps the minus on negatives", () => {
  assert.equal(signedFixed(-1.5), "-1.50");
  assert.equal(signedFixed(0.534), "+0.53");
  assert.equal(signedFixed(3, 1), "+3.0");
});
