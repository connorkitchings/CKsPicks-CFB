import assert from "node:assert/strict";
import test from "node:test";
import { layoutTrajectoryEndpoints } from "./chart-trajectory-layout.ts";
import { parseTrajectoryMetric } from "./chart-config.ts";
import { trajectorySeries, type AdjustedRow, type RosterRow, type Side } from "./charts.ts";

const roster: RosterRow[] = [
  { team: "Alabama", conference: "SEC" },
  { team: "Georgia", conference: "SEC" },
  { team: "Tulane", conference: "American Athletic" },
  { team: "Wyoming", conference: "Mountain West" },
];

function adjusted(asOfWeek: number, team: string, role: Side, value: number, epaN = 100): AdjustedRow {
  return {
    asOfWeek, team, role, rawEpaPerPlay: value, venueCorrection: 0, opponentAdjustment: 0,
    adjustedEpaPerPlay: value, epaN, games: 2, adjustedRank: 1, cohortSize: 4,
  };
}

/** Windows as_of 3, 4, 5 (Through Weeks 2-4), plus an as_of 2 window that is never charted. */
const rows: AdjustedRow[] = [
  adjusted(2, "Alabama", "offense", 9), adjusted(2, "Alabama", "defense", 9),
  // Alabama: every window, both roles.
  adjusted(3, "Alabama", "offense", 0.3, 100), adjusted(3, "Alabama", "defense", 0.1, 100),
  adjusted(4, "Alabama", "offense", 0.2, 200), adjusted(4, "Alabama", "defense", 0.0, 200),
  adjusted(5, "Alabama", "offense", 0.25, 300), adjusted(5, "Alabama", "defense", 0.05, 300),
  // Georgia: missing window 4 entirely, so a gap between two one-window runs.
  adjusted(3, "Georgia", "offense", 0.1, 300), adjusted(3, "Georgia", "defense", 0.2, 300),
  adjusted(5, "Georgia", "offense", 0.15, 100), adjusted(5, "Georgia", "defense", 0.1, 100),
  // Tulane: offense every window, defense only in window 4.
  adjusted(3, "Tulane", "offense", -0.1), adjusted(4, "Tulane", "offense", -0.05), adjusted(5, "Tulane", "offense", 0),
  adjusted(4, "Tulane", "defense", 0.2),
  // Not a roster team: ignored.
  adjusted(3, "Idaho", "offense", 5), adjusted(3, "Idaho", "defense", -5),
];

const seriesOf = (data: ReturnType<typeof trajectorySeries>, team: string) => data.series.find((s) => s.team === team)!;
const close = (actual: number | null, expected: number) => {
  assert.ok(actual !== null && Math.abs(actual - expected) < 1e-12, `${actual} != ${expected}`);
};

test("trajectory: x is Through Week as_of_week - 1 from Week 2 on; teams with no value are unavailable", () => {
  const data = trajectorySeries(roster, rows, "net");
  assert.deepEqual(data.weeks, [2, 3, 4]);
  assert.deepEqual(data.series.map((s) => s.team), ["Alabama", "Georgia", "Tulane"]);
  assert.deepEqual(data.unavailable, ["Wyoming"]);
  const alabama = seriesOf(data, "Alabama");
  assert.equal(alabama.segments.length, 1);
  assert.deepEqual(alabama.segments[0].map((p) => p.week), [2, 3, 4]);
  close(alabama.values[0], 0.2);
  close(alabama.values[2], 0.2);
});

test("trajectory: a missing window is a gap with no interpolation, and a one-window run is a dot", () => {
  const georgia = seriesOf(trajectorySeries(roster, rows, "offense"), "Georgia");
  assert.deepEqual(georgia.values, [0.1, null, 0.15]);
  assert.deepEqual(georgia.segments, [[{ week: 2, value: 0.1 }], [{ week: 4, value: 0.15 }]]);
});

test("trajectory: net needs both roles in a window; offense and defense read their own role", () => {
  const net = seriesOf(trajectorySeries(roster, rows, "net"), "Tulane");
  assert.equal(net.values[0], null);
  close(net.values[1], -0.25);
  assert.equal(net.values[2], null);
  assert.deepEqual(net.segments.map((run) => run.map((p) => p.week)), [[3]], "a lone net window is a dot");
  assert.deepEqual(seriesOf(trajectorySeries(roster, rows, "offense"), "Tulane").values, [-0.1, -0.05, 0]);
  assert.deepEqual(seriesOf(trajectorySeries(roster, rows, "defense"), "Tulane").values, [null, 0.2, null]);
});

test("trajectory: weekly averages are play-weighted over teams with both roles, as in adjustedPoints", () => {
  const offense = trajectorySeries(roster, rows, "offense").average;
  // Window 3: Alabama 0.3 x 100 and Georgia 0.1 x 300 (Tulane lacks defense, so it is excluded).
  close(offense[0], (0.3 * 100 + 0.1 * 300) / 400);
  // Window 4: Alabama (200 plays) and Tulane (100 plays) have both roles; Georgia has none.
  close(offense[1], (0.2 * 200 + -0.05 * 100) / 300);
  const defense = trajectorySeries(roster, rows, "defense").average;
  close(defense[0], (0.1 * 100 + 0.2 * 300) / 400);
  const net = trajectorySeries(roster, rows, "net").average;
  close(net[2], (0.25 * 300 + 0.15 * 100) / 400 - (0.05 * 300 + 0.1 * 100) / 400);
});

test("trajectory: only the defense axis is inverted", () => {
  assert.equal(trajectorySeries(roster, rows, "defense").invertY, true);
  assert.equal(trajectorySeries(roster, rows, "offense").invertY, false);
  assert.equal(trajectorySeries(roster, rows, "net").invertY, false);
});

test("trajectory: no stored window from Week 2 on gives no series", () => {
  const data = trajectorySeries(roster, rows.filter((r) => r.asOfWeek === 2), "net");
  assert.deepEqual(data.weeks, []);
  assert.deepEqual(data.series, []);
  assert.deepEqual(data.average, []);
  assert.equal(data.unavailable.length, roster.length);
});

test("trajectory metric param: offense and defense parse; anything else is net", () => {
  assert.equal(parseTrajectoryMetric("offense"), "offense");
  assert.equal(parseTrajectoryMetric("defense"), "defense");
  for (const raw of ["net", undefined, null, "Offense", ["offense"], ""]) assert.equal(parseTrajectoryMetric(raw), "net");
});


test("trajectory endpoint logos: ties are deterministic, bounded and separated even at plot edges", () => {
  for (const y of [18, 250, 548]) {
    const endpoints = Array.from({ length: 20 }, (_, i) => ({ team: `Team ${String(i).padStart(2, "0")}`, y, size: i === 0 ? 30 : 20 }));
    const layout = layoutTrajectoryEndpoints(endpoints, 18, 548);
    assert.deepEqual(layout, layoutTrajectoryEndpoints([...endpoints].reverse(), 18, 548));
    const positions = [...layout.values()];
    assert.ok(positions[0].y - positions[0].size / 2 >= 18);
    assert.ok(positions.at(-1)!.y + positions.at(-1)!.size / 2 <= 548);
    for (let i = 1; i < positions.length; i++) {
      assert.ok(positions[i].y - positions[i].size / 2 >= positions[i - 1].y + positions[i - 1].size / 2 + 4);
      assert.equal(positions[i].size, 20);
    }
  }
});

test("trajectory endpoint logos: oversized groups fit the rail without overlapping", () => {
  const endpoints = Array.from({ length: 138 }, (_, i) => ({ team: `Team ${i}`, y: 250, size: 20 }));
  const positions = [...layoutTrajectoryEndpoints(endpoints, 18, 548).values()];
  assert.ok(positions[0].y - positions[0].size / 2 >= 18 - 1e-9);
  assert.ok(positions.at(-1)!.y + positions.at(-1)!.size / 2 <= 548 + 1e-9);
  for (let i = 1; i < positions.length; i++) {
    assert.ok(positions[i].y - positions[i].size / 2 >= positions[i - 1].y + positions[i - 1].size / 2);
  }
});
