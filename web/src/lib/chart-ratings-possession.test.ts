import assert from "node:assert/strict";
import test from "node:test";
import { describePossessionPoint, describeRatingPoint, parsePossessionMetric, parseRatingMetric } from "./chart-config.ts";
import {
  possessionPoints,
  ratingTrajectorySeries,
  type PossessionMetric,
  type PossessionRow,
  type RatingSnapshotRow,
  type RosterRow,
  type Side,
  type TrajectoryData,
} from "./charts.ts";

const roster: RosterRow[] = [
  { team: "Alabama", conference: "SEC" },
  { team: "Georgia", conference: "SEC" },
  { team: "Tulane", conference: "American Athletic" },
  { team: "Wyoming", conference: "Mountain West" },
];

const close = (actual: number | null | undefined, expected: number) => {
  assert.ok(typeof actual === "number" && Math.abs(actual - expected) < 1e-12, `${actual} != ${expected}`);
};

// ---------------------------------------------------------------------------
// V5 rating trajectory
// ---------------------------------------------------------------------------

function snapshot(week: number, team: string, offense: number, defense: number, variance = 0.04): RatingSnapshotRow {
  return {
    week, team,
    offenseRating: offense, offenseVariance: variance,
    defenseRating: defense, defenseVariance: variance * 4,
    overallRating: (offense + defense) / 2, overallVariance: variance * 9,
  };
}

/** Weeks 0-2. Tulane misses week 1; Wyoming has no snapshot; Idaho is not a roster team. */
const snapshots: RatingSnapshotRow[] = [
  snapshot(0, "Alabama", 1.0, 0.8), snapshot(1, "Alabama", 1.2, 0.9), snapshot(2, "Alabama", 1.1, 1.0),
  snapshot(0, "Georgia", 0.6, 1.2), snapshot(1, "Georgia", 1.2, 0.2), snapshot(2, "Georgia", 0.9, 1.4),
  snapshot(0, "Tulane", -0.2, 0.1), snapshot(2, "Tulane", 0.0, -0.3),
  snapshot(0, "Idaho", 9, 9),
];

const ratingOf = (team: string, metric: Parameters<typeof ratingTrajectorySeries>[2] = "overall") =>
  ratingTrajectorySeries(roster, snapshots, metric).series.find((s) => s.team === team)!;

test("rating trajectory: every stored week from Week 0 is plotted; teams without a snapshot are unavailable", () => {
  const data = ratingTrajectorySeries(roster, snapshots, "overall");
  const drawable: TrajectoryData = data; // the trajectory chart draws it unchanged
  assert.deepEqual(drawable.weeks, [0, 1, 2]);
  assert.deepEqual(data.series.map((s) => s.team), ["Alabama", "Georgia", "Tulane"]);
  assert.deepEqual(data.unavailable, ["Wyoming"]);
  assert.deepEqual(data.ranked, [3, 2, 3], "Idaho is never ranked");
});

test("rating trajectory: a missing team-week is a gap, never interpolated", () => {
  const tulane = ratingOf("Tulane", "offense");
  assert.deepEqual(tulane.values, [-0.2, null, 0.0]);
  assert.deepEqual(tulane.segments, [[{ week: 0, value: -0.2 }], [{ week: 2, value: 0.0 }]]);
  assert.deepEqual([tulane.sd[1], tulane.ranks[1]], [null, null]);
});

test("rating trajectory: the metric picks its own rating and standard deviation", () => {
  close(ratingOf("Alabama", "offense").values[1], 1.2);
  close(ratingOf("Alabama", "defense").values[1], 0.9);
  close(ratingOf("Alabama", "overall").values[1], 1.05);
  close(ratingOf("Alabama", "offense").sd[0], Math.sqrt(0.04));
  close(ratingOf("Alabama", "defense").sd[0], Math.sqrt(0.16));
  close(ratingOf("Alabama", "overall").sd[0], Math.sqrt(0.36));
});

test("rating trajectory: higher is better on every metric, so no axis is inverted and the best rating ranks first", () => {
  for (const metric of ["overall", "offense", "defense"] as const) assert.equal(ratingTrajectorySeries(roster, snapshots, metric).invertY, false);
  // Week 2 defense: Georgia 1.4, Alabama 1.0, Tulane -0.3.
  assert.deepEqual(["Georgia", "Alabama", "Tulane"].map((team) => ratingOf(team, "defense").ranks[2]), [1, 2, 3]);
});

test("rating trajectory: tied ratings share a competition rank", () => {
  // Week 1 offense: Alabama and Georgia both 1.2; with a third team the next rank would be 3.
  const tied = [...snapshots, snapshot(1, "Tulane", 0.5, 0.5)];
  const ranks = (team: string) => ratingTrajectorySeries(roster, tied, "offense").series.find((s) => s.team === team)!.ranks[1];
  assert.deepEqual(["Alabama", "Georgia", "Tulane"].map(ranks), [1, 1, 3]);
});

test("rating trajectory: the reference is the unweighted mean of all roster teams, so a group subset leaves it unchanged", () => {
  const data = ratingTrajectorySeries(roster, snapshots, "offense");
  close(data.average[0], (1.0 + 0.6 - 0.2) / 3);
  close(data.average[1], 1.2);
  const sec = ratingTrajectorySeries(roster.filter((r) => r.conference === "SEC"), snapshots, "offense");
  assert.notEqual(sec.average[0], data.average[0], "the full roster, not the group, sets the reference");
  assert.equal(ratingOf("Tulane", "offense").ranks[0], 3, "ranks are national");
});

test("rating trajectory: no snapshot gives no series; a duplicate team-week is a data error", () => {
  const empty = ratingTrajectorySeries(roster, [], "overall");
  assert.deepEqual([empty.weeks, empty.series, empty.average], [[], [], []]);
  assert.equal(empty.unavailable.length, roster.length);
  assert.throws(() => ratingTrajectorySeries(roster, [...snapshots, snapshot(0, "Alabama", 0, 0)], "overall"), /more than one current row/);
});

test("rating tooltip: rating ± standard deviation and the weekly rank", () => {
  const data = ratingTrajectorySeries(roster, snapshots, "offense");
  const alabama = data.series.find((s) => s.team === "Alabama")!;
  assert.equal(describeRatingPoint(data, alabama, 0, "offense"), "Alabama (SEC), Through Week 0: V5 offense rating 1.00 ± 0.20, 1st of 3");
});

test("rating metric param: offense and defense parse; anything else is overall", () => {
  assert.equal(parseRatingMetric("offense"), "offense");
  assert.equal(parseRatingMetric("defense"), "defense");
  for (const raw of ["overall", "net", undefined, null, "Defense", ["defense"], ""]) assert.equal(parseRatingMetric(raw), "overall");
});

// ---------------------------------------------------------------------------
// Possession efficiency
// ---------------------------------------------------------------------------

function possession(
  team: string, role: Side, adjusted: number | null, exposure: number | null = 30, measurementId: PossessionMetric = "ppp",
): PossessionRow {
  return {
    asOfWeek: 4, team, role, measurementId,
    rawValue: adjusted === null ? null : adjusted + 0.1, adjustedValue: adjusted,
    opponentAdjustment: adjusted === null ? null : 0.1,
    adjustedRank: 1, cohortSize: 4, primaryExposure: exposure, games: 3,
  };
}

/** Wyoming lacks a defense row; Tulane's defense ppp has no adjusted value. */
const possessionRows: PossessionRow[] = [
  possession("Alabama", "offense", 2.8, 40), possession("Alabama", "defense", 1.4, 20),
  possession("Georgia", "offense", 2.4, 20), possession("Georgia", "defense", 1.4, 40),
  possession("Tulane", "offense", 2.0), possession("Tulane", "defense", null),
  possession("Wyoming", "offense", 1.6),
  possession("Alabama", "offense", 0.5, 40, "epa_per_possession"), possession("Alabama", "defense", -0.2, 20, "epa_per_possession"),
  possession("Tulane", "offense", 0.1, 30, "epa_per_possession"), possession("Tulane", "defense", 0.3, 30, "epa_per_possession"),
  possession("Idaho", "offense", 9), possession("Idaho", "defense", 9),
];

test("possession: offense on x, defense allowed on y (inverted); teams missing a role are unavailable", () => {
  const data = possessionPoints(roster, possessionRows, "ppp");
  assert.deepEqual(data.points.map((p) => [p.team, p.x, p.y]), [["Alabama", 2.8, 1.4], ["Georgia", 2.4, 1.4]]);
  assert.deepEqual(data.unavailable, ["Tulane", "Wyoming"], "a null adjusted value is a missing role");
  assert.deepEqual([data.invertX, data.invertY], [false, true]);
  assert.deepEqual(data.points.map((p) => p.n), [60, 60], "n is the summed possessions");
});

test("possession: the metric selects its own measurement rows", () => {
  const data = possessionPoints(roster, possessionRows, "epa_per_possession");
  assert.deepEqual(data.points.map((p) => [p.team, p.x, p.y]), [["Alabama", 0.5, -0.2], ["Tulane", 0.1, 0.3]]);
  assert.deepEqual(data.unavailable, ["Georgia", "Wyoming"]);
});

test("possession: pooled averages are weighted by possessions per role, and a missing exposure weighs zero", () => {
  const data = possessionPoints(roster, possessionRows, "ppp");
  close(data.average?.x, (2.8 * 40 + 2.4 * 20) / 60);
  close(data.average?.y, (1.4 * 20 + 1.4 * 40) / 60);
  const unweighted = possessionPoints(roster, [...possessionRows.filter((r) => r.team !== "Georgia"),
    possession("Georgia", "offense", 2.4, null), possession("Georgia", "defense", 1.4, null)], "ppp");
  assert.equal(unweighted.points.length, 2, "a team without exposure is still plotted");
  close(unweighted.average?.x, 2.8);
  assert.equal(possessionPoints(roster, [], "ppp").average, null);
});

test("possession: ranks are recomputed over the plotted teams; defense allowed ranks lower first and ties share a rank", () => {
  const data = possessionPoints(roster, possessionRows, "ppp");
  assert.deepEqual(data.ranks, { Alabama: { offense: 1, defense: 1 }, Georgia: { offense: 2, defense: 1 } });
  const epa = possessionPoints(roster, possessionRows, "epa_per_possession");
  assert.deepEqual(epa.ranks, { Alabama: { offense: 1, defense: 1 }, Tulane: { offense: 2, defense: 2 } });
});

test("possession tooltip: raw, adjusted, opponent adjustment, games and both ranks", () => {
  const data = possessionPoints(roster, possessionRows, "ppp");
  assert.equal(
    describePossessionPoint(data.points[1], data, "ppp"),
    "Georgia (SEC), points per possession: offense adjusted 2.40 (raw 2.50, opponent adjustment 0.10, 3 games), 2nd of 2; " +
      "defense allowed adjusted 1.40 (raw 1.50, opponent adjustment 0.10, 3 games), 1st of 2",
  );
});

test("possession metric param: PPA per possession under its stored epa id or a ppa alias, in either spelling; anything else is points per possession", () => {
  for (const raw of ["epa_per_possession", "epa-per-possession", "ppa_per_possession", "ppa-per-possession"]) assert.equal(parsePossessionMetric(raw), "epa_per_possession");
  for (const raw of ["ppp", undefined, null, "EPA", "PPA", "epa_per_possession_x", ["epa_per_possession"], ""]) assert.equal(parsePossessionMetric(raw), "ppp");
});
