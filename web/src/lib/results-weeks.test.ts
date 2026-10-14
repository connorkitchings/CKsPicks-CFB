import assert from "node:assert/strict";
import test from "node:test";

import { selectGradedWeeks, type SelectedWeekRun } from "./results-weeks.ts";

const V5 = "v5-possession-ppp-rho060-exposure";

function run(overrides: Partial<SelectedWeekRun>): SelectedWeekRun {
  return {
    week: 1,
    state: "scored",
    evidenceClass: "live",
    modelId: V5,
    validation: {},
    gradedGames: 0,
    ...overrides,
  };
}

function displayOnly(overrides: Partial<SelectedWeekRun>): SelectedWeekRun {
  return run({ state: "published", evidenceClass: "pending", validation: { display_only: true }, ...overrides });
}

test("a scored run is listed whether or not result rows were counted", () => {
  assert.deepEqual(selectGradedWeeks([run({ week: 5 })]), [5]);
});

test("a published display-only run with finals is listed", () => {
  assert.deepEqual(selectGradedWeeks([displayOnly({ week: 6, gradedGames: 52 })]), [6]);
});

test("a published display-only run without finals is not listed", () => {
  assert.deepEqual(selectGradedWeeks([displayOnly({ week: 7, gradedGames: 0 })]), []);
});

test("a published run that is not display-only waits for scoring even with finals", () => {
  assert.deepEqual(
    selectGradedWeeks([run({ week: 6, state: "published", evidenceClass: "pending", gradedGames: 52 })]),
    [],
  );
});

test("a run with an ineligible evidence class is not listed", () => {
  assert.deepEqual(selectGradedWeeks([run({ week: 4, evidenceClass: "missed" })]), []);
  assert.deepEqual(selectGradedWeeks([displayOnly({ week: 6, evidenceClass: "missed", gradedGames: 52 })]), []);
});

test("a display-only preview run is not listed", () => {
  assert.deepEqual(selectGradedWeeks([displayOnly({ week: 6, state: "preview", gradedGames: 52 })]), []);
});

test("weeks come back ascending without duplicates", () => {
  assert.deepEqual(
    selectGradedWeeks([
      displayOnly({ week: 6, gradedGames: 3 }),
      run({ week: 2 }),
      run({ week: 0 }),
      run({ week: 2 }),
      displayOnly({ week: 7, gradedGames: 0 }),
    ]),
    [0, 2, 6],
  );
});
