import assert from "node:assert/strict";
import test from "node:test";
import { nearestScatterTeams } from "./scatter-selection.ts";

test("scatter tap uses a 24 screen-pixel radius including its boundary", () => {
  const points = [{ team: "Inside", x: 24, y: 0 }, { team: "Outside", x: 24.01, y: 0 }];
  assert.deepEqual(nearestScatterTeams(points, 0, 0), ["Inside"]);
  assert.deepEqual(nearestScatterTeams(points, 100, 100), []);
});

test("scatter tap selects the closest point without ambiguous distant alternatives", () => {
  assert.deepEqual(nearestScatterTeams([{ team: "Near", x: 2, y: 3 }, { team: "Far", x: 13, y: 0 }], 0, 0), ["Near"]);
});

test("scatter ambiguity includes the 8px boundary and offers at most three stable names", () => {
  const points = ["D", "C", "B", "A"].map((team) => ({ team, x: 5, y: 0 }));
  assert.deepEqual(nearestScatterTeams(points, 0, 0), ["A", "B", "C"]);
  assert.deepEqual(nearestScatterTeams([{ team: "A", x: 1, y: 0 }, { team: "B", x: 9, y: 0 }, { team: "C", x: 9.01, y: 0 }], 0, 0), ["A", "B"]);
});

test("scatter hit testing respects translated screen coordinates", () => {
  assert.deepEqual(nearestScatterTeams([{ team: "Team", x: 106, y: 207 }], 100, 200), ["Team"]);
});
