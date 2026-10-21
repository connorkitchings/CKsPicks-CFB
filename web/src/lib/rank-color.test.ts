import assert from "node:assert/strict";
import test from "node:test";

import { rankColorMix } from "./rank-color.ts";

test("rank 1 is the green end and the last rank the red end", () => {
  assert.equal(rankColorMix(1), 0);
  assert.equal(rankColorMix(138), 1);
  assert.equal(rankColorMix(16, 16), 1);
});

test("the midpoint rank is neutral", () => {
  assert.equal(rankColorMix(69.5), 0.5);
  assert.ok(Math.abs((rankColorMix(69) as number) - 0.5) < 0.005);
});

test("the mix rises monotonically with the rank number", () => {
  let previous = -1;
  for (let rank = 1; rank <= 138; rank += 1) {
    const mix = rankColorMix(rank) as number;
    assert.ok(mix > previous);
    previous = mix;
  }
});

test("ranks past the total clamp to the red end", () => {
  assert.equal(rankColorMix(500), 1);
  assert.equal(rankColorMix(5, 3), 1);
});

test("invalid ranks have no color", () => {
  for (const rank of [null, undefined, Number.NaN, Infinity, 0, -3]) assert.equal(rankColorMix(rank), null);
});

test("a degenerate total stays at the green end instead of dividing by zero", () => {
  assert.equal(rankColorMix(1, 1), 0);
  assert.equal(rankColorMix(1, Number.NaN), 0);
});
