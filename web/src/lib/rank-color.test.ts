import assert from "node:assert/strict";
import test from "node:test";

import { rankColorMix } from "./rank-color.ts";

test("rank 1 is the green end and the last rank the red end", () => {
  assert.equal(rankColorMix(1), 0);
  assert.equal(rankColorMix(138), 1);
  assert.equal(rankColorMix(16, 16), 1);
});

test("the midpoint rank is exactly the amber midpoint", () => {
  assert.equal(rankColorMix(69.5), 0.5);
  assert.ok(Math.abs((rankColorMix(69) as number) - 0.5) < 0.01);
  assert.equal(rankColorMix(8.5, 16), 0.5);
});

test("the mix never decreases with the rank number and is strictly rising between the plateaus", () => {
  let previous = -1;
  for (let rank = 1; rank <= 138; rank += 1) {
    const mix = rankColorMix(rank) as number;
    assert.ok(mix >= previous);
    if (rank > 33 && rank < 106) assert.ok(mix > previous);
    previous = mix;
  }
});

test("the outer ranks saturate to solid green and solid red", () => {
  for (let rank = 1; rank <= 30; rank += 1) assert.equal(rankColorMix(rank), 0);
  for (let rank = 108; rank <= 138; rank += 1) assert.equal(rankColorMix(rank), 1);
  assert.ok((rankColorMix(35) as number) < 0.02);
  assert.ok((rankColorMix(104) as number) > 0.98 - 0.05);
});

test("ranks 35, 69 and 104 are clearly different", () => {
  const [a, b, c] = [35, 69.5, 104].map((rank) => rankColorMix(rank) as number);
  assert.ok(b - a > 0.4);
  assert.ok(c - b > 0.4);
});

test("the curve is symmetric around the midpoint", () => {
  for (let rank = 1; rank <= 138; rank += 1) {
    const mirrored = rankColorMix(139 - rank) as number;
    assert.ok(Math.abs((rankColorMix(rank) as number) + mirrored - 1) < 1e-12);
  }
});

test("other totals scale the plateaus proportionally", () => {
  assert.equal(rankColorMix(1, 20), 0);
  assert.equal(rankColorMix(5, 20), 0);
  assert.equal(rankColorMix(16, 20), 1);
  assert.equal(rankColorMix(20, 20), 1);
  assert.equal(rankColorMix(2, 3), 0.5);
  assert.ok((rankColorMix(10, 20) as number) > 0.4 && (rankColorMix(10, 20) as number) < 0.6);
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
