import assert from "node:assert/strict";
import test from "node:test";
import {
  normalCdf,
  calculateWinProbabilities,
  calculateProjectedPoints,
  getRankBadgeClass,
} from "./matchup-math.ts";

test("normalCdf computes accurate standard normal probabilities", () => {
  // z = 0 -> 50%
  assert.equal(Math.round(normalCdf(0) * 1000) / 1000, 0.5);

  // z = 1 -> ~84.1%
  const plusOne = normalCdf(1);
  assert.ok(plusOne > 0.84 && plusOne < 0.843);

  // z = -1 -> ~15.9%
  const minusOne = normalCdf(-1);
  assert.ok(minusOne > 0.157 && minusOne < 0.16);

  // z = 2 -> ~97.7%
  const plusTwo = normalCdf(2);
  assert.ok(plusTwo > 0.975 && plusTwo < 0.979);

  // Symmetry: P(Z <= -z) + P(Z <= z) = 1
  assert.equal(Math.round((normalCdf(1.5) + normalCdf(-1.5)) * 1000) / 1000, 1.0);
});

test("calculateWinProbabilities returns correct home and away percentages", () => {
  // Even matchup
  const even = calculateWinProbabilities(0);
  assert.equal(even.homeWinProb, 50);
  assert.equal(even.awayWinProb, 50);

  // Home favored by 7 with std dev 13.5
  const homeFavored = calculateWinProbabilities(7, 13.5);
  assert.ok(homeFavored.homeWinProb > 69 && homeFavored.homeWinProb < 71);
  assert.equal(Math.round(homeFavored.homeWinProb + homeFavored.awayWinProb), 100);

  // Away favored by 14 with std dev 13.5
  const awayFavored = calculateWinProbabilities(-14, 13.5);
  assert.ok(awayFavored.awayWinProb > 84 && awayFavored.awayWinProb < 86);
  assert.equal(Math.round(awayFavored.homeWinProb + awayFavored.awayWinProb), 100);
});

test("calculateProjectedPoints splits predicted total by margin", () => {
  // Alabama at Mississippi State: Total 57.6, Alabama favored by 3.2 (home margin -3.2)
  const bamaMsst = calculateProjectedPoints(57.6, -3.2);
  assert.equal(bamaMsst.awayProjPoints, 30.4);
  assert.equal(bamaMsst.homeProjPoints, 27.2);
  assert.equal(Math.round((bamaMsst.awayProjPoints + bamaMsst.homeProjPoints) * 10) / 10, 57.6);

  // Georgia vs Kentucky: Total 48.0, Georgia favored by 24 (home margin +24)
  const ugaUky = calculateProjectedPoints(48.0, 24.0);
  assert.equal(ugaUky.homeProjPoints, 36.0);
  assert.equal(ugaUky.awayProjPoints, 12.0);
});

test("getRankBadgeClass assigns appropriate color classes by tier", () => {
  assert.ok(getRankBadgeClass(4).includes("accent")); // Top 25
  assert.ok(getRankBadgeClass(45).includes("cyan")); // 26-60
  assert.ok(getRankBadgeClass(75).includes("surface-inset")); // 61-90
  assert.ok(getRankBadgeClass(110).includes("loss")); // 91+
});
