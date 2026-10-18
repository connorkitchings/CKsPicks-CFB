import assert from "node:assert/strict";
import test from "node:test";
import { describeScheduleRow, scheduleAxisLabel } from "./chart-config.ts";
import { scheduleReading, scheduleRows, scheduleSubset, type AdjustedRow, type RosterRow, type ScheduleRow, type Side } from "./charts.ts";

function adjustedRow(team: string, role: Side, raw: number, venue: number, opponent: number): AdjustedRow {
  return {
    asOfWeek: 4, team, role, rawEpaPerPlay: raw, venueCorrection: venue, opponentAdjustment: opponent,
    adjustedEpaPerPlay: raw - venue - opponent, epaN: 200, games: 3, adjustedRank: 1, cohortSize: 3,
  };
}

const roster: RosterRow[] = [
  { team: "Alabama", conference: "SEC" },
  { team: "Tulane", conference: "American Athletic" },
  { team: "Wyoming", conference: "Mountain West" },
];

/**
 * `count` teams T01..Tnn with the given offense effects (default: strictly descending),
 * built through `scheduleRows` from rows given in reverse order, so the transform sorts them.
 */
function rows(count: number, effect: (index: number) => number = (i) => -i): ScheduleRow[] {
  const teams = Array.from({ length: count }, (_, i) => `T${String(i + 1).padStart(2, "0")}`);
  const source = teams.map((team, i) => adjustedRow(team, "offense", 0.1, 0, -effect(i))).reverse();
  return scheduleRows(teams.map((team) => ({ team, conference: null })), source, "offense").rows;
}

test("schedule effect: offense is adjusted − neutral (= −opponent adjustment); defense is neutral − adjusted (= +opponent adjustment)", () => {
  const source = [
    // Raw understated by a tough schedule on offense: the adjuster raises the team.
    adjustedRow("Alabama", "offense", 0.2, 0.01, -0.03),
    adjustedRow("Alabama", "defense", 0.05, -0.01, 0.02),
    adjustedRow("Tulane", "offense", 0.1, 0.0, 0.04),
    adjustedRow("Tulane", "defense", 0.1, 0.0, -0.05),
  ];
  const offense = scheduleRows(roster, source, "offense");
  const alabama = offense.rows.find((r) => r.team === "Alabama")!;
  assert.ok(Math.abs(alabama.neutral - 0.19) < 1e-12, "neutral = raw − venue correction");
  assert.ok(Math.abs(alabama.effect - 0.03) < 1e-12);
  assert.ok(Math.abs(offense.rows.find((r) => r.team === "Tulane")!.effect + 0.04) < 1e-12);
  assert.deepEqual(offense.rows.map((r) => r.team), ["Alabama", "Tulane"], "effect descending");
  assert.deepEqual(offense.unavailable, ["Wyoming"]);
  assert.equal(offense.invert, false);

  const defense = scheduleRows(roster, source, "defense");
  assert.ok(Math.abs(defense.rows.find((r) => r.team === "Alabama")!.effect - 0.02) < 1e-12, "defense effect = +opponent adjustment");
  assert.ok(Math.abs(defense.rows.find((r) => r.team === "Tulane")!.effect + 0.05) < 1e-12);
  assert.equal(defense.invert, true, "defense axis inverted");
  assert.match(scheduleAxisLabel("defense"), /allowed.*inverted/);
});

test("schedule readings use only the two contract labels", () => {
  assert.equal(scheduleReading(0.01), "raw understated: tougher opponents than average");
  assert.equal(scheduleReading(-0.01), "raw inflated: weaker opponents");
  assert.equal(scheduleReading(0), null);
  const [row] = scheduleRows(roster, [adjustedRow("Tulane", "defense", 0.1, 0.0, -0.05)], "defense").rows;
  const text = describeScheduleRow(row, "defense");
  assert.match(text, /raw \+0\.100, venue correction 0\.000, venue-neutral \+0\.100, adjusted \+0\.150 PPA\/play allowed; schedule effect -0\.050 \(raw inflated: weaker opponents\)/);
  assert.doesNotMatch(text, /helped|hurt/);
});

test("equal effects sort by team name", () => {
  const source = ["Wyoming", "Alabama", "Tulane"].map((team) => adjustedRow(team, "offense", 0.1, 0, 0.01));
  assert.deepEqual(scheduleRows(roster, source, "offense").rows.map((r) => r.team), ["Alabama", "Tulane", "Wyoming"]);
});

test("a long group shows the first and last 15, cut strictly with boundary ties by name", () => {
  // 40 teams; T14..T17 share one effect across the top boundary, T24..T27 across the bottom one.
  const group = rows(40, (i) => (i >= 13 && i <= 16 ? -13 : i >= 23 && i <= 26 ? -23 : -i));
  const subset = scheduleSubset(group, { showAll: false, highlight: null });
  assert.equal(subset.top.length, 15);
  assert.equal(subset.bottom.length, 15);
  assert.deepEqual(subset.top.slice(-2).map((r) => r.team), ["T14", "T15"], "tie at the top cut keeps names T14, T15 only");
  assert.deepEqual(subset.bottom.slice(0, 2).map((r) => r.team), ["T26", "T27"], "tie at the bottom cut keeps T26, T27 only");
  assert.equal(subset.omitted, 10);
  assert.equal(subset.extra, null);
});

test("30 or fewer teams, overlapping ends, or Show all list every team once", () => {
  for (const count of [5, 29, 30]) {
    const subset = scheduleSubset(rows(count), { showAll: false, highlight: "T03" });
    assert.equal(subset.top.length, count, `${count} teams`);
    assert.deepEqual(subset.bottom, []);
    assert.equal(subset.omitted, 0);
    assert.equal(subset.extra, null);
  }
  const all = scheduleSubset(rows(138), { showAll: true, highlight: "T41" });
  assert.equal(all.top.length, 138);
  assert.equal(new Set(all.top.map((r) => r.team)).size, 138);
  assert.equal(all.extra, null);
});

test("a highlighted team outside the shown rows becomes an extra row with its position", () => {
  const group = rows(138);
  const subset = scheduleSubset(group, { showAll: false, highlight: "T41" });
  assert.deepEqual(subset.extra && { team: subset.extra.row.team, position: subset.extra.position, total: subset.extra.total }, { team: "T41", position: 41, total: 138 });
  assert.ok(!subset.top.concat(subset.bottom).some((r) => r.team === "T41"));
  // Shown teams (first 15, last 15) and unknown teams get no extra row.
  for (const team of ["T15", "T124", "Nowhere"]) assert.equal(scheduleSubset(group, { showAll: false, highlight: team }).extra, null, team);
  assert.ok(scheduleSubset(group, { showAll: false, highlight: "T16" }).extra);
  assert.ok(scheduleSubset(group, { showAll: false, highlight: "T123" }).extra);
});
