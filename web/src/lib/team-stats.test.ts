import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  buildMatchupStats,
  buildUnitRows,
  cohortSizeOf,
  formatMetric,
  gamesBehind,
  getRankBadgeClass,
  groupUnitRows,
  SECTION_LABELS,
  UNIT_METRICS,
  type TeamStatRow,
} from "./team-stats.ts";

const row = (team: string, role: "offense" | "defense", metric: string, value: number | null, rank: number | null): TeamStatRow => ({
  team, role, metric, value, n: 10, games: 4, rank, cohortSize: rank === null ? null : 130,
});

test("formatMetric formats each kind and shows a dash for missing values", () => {
  assert.equal(formatMetric("epa", 0.234), "+0.23");
  assert.equal(formatMetric("epa", -0.05), "−0.05");
  assert.equal(formatMetric("pct", 0.4567), "45.7%");
  assert.equal(formatMetric("pts", 4.1), "4.10");
  assert.equal(formatMetric("field", 31.25), "Own 31.3");
  assert.equal(formatMetric("num", 5.857), "5.9");
  assert.equal(formatMetric("num", null), "—");
  assert.equal(formatMetric("pct", null), "—");
  assert.equal(formatMetric("pct", Number.NaN), "—");
});

test("buildUnitRows pairs the offense with the OPPOSING defense, never the same team's", () => {
  const rows = [
    row("A", "offense", "epa_pass", 0.3, 5),
    row("A", "defense", "epa_pass", 0.9, 120),
    row("B", "defense", "epa_pass", -0.1, 4),
    row("B", "offense", "epa_pass", 0.0, 60),
  ];
  const out = buildUnitRows(rows, "A", "B").find((r) => r.key === "epa_pass");
  assert.deepEqual(
    [out?.offenseValue, out?.offenseRank, out?.defenseValue, out?.defenseRank],
    ["+0.30", 5, "−0.10", 4],
  );
});

test("buildUnitRows returns every metric and tolerates a team with no rows", () => {
  const out = buildUnitRows([], "A", "B");
  assert.equal(out.length, UNIT_METRICS.length);
  assert.equal(out.length, 14);
  assert.ok(out.every((r) => r.offenseValue === "—" && r.offenseRank === null && r.defenseRank === null));
});

test("null rank keeps the value but shows no national rank", () => {
  const out = buildUnitRows([row("A", "offense", "epa_rush", 0.1, null)], "A", "B").find((r) => r.key === "epa_rush");
  assert.equal(out?.offenseValue, "+0.10");
  assert.equal(out?.offenseRank, null);
});

test("gamesBehind and cohortSizeOf", () => {
  const rows = [row("A", "offense", "epa_pass", 0.1, 3), { ...row("B", "offense", "epa_pass", 0.1, 4), games: 2 }];
  assert.equal(gamesBehind(rows, "A"), 4);
  assert.equal(gamesBehind(rows, "Z"), 0);
  assert.equal(cohortSizeOf(rows), 130);
  assert.equal(cohortSizeOf([]), null);
});

test("rank badge tiers", () => {
  assert.match(getRankBadgeClass(10), /accent/);
  assert.match(getRankBadgeClass(120), /loss/);
  assert.match(getRankBadgeClass(null), /ink-faint/);
  // Relative to the ranked pool: #10 of 16 is bottom-half, not "top 25".
  assert.match(getRankBadgeClass(10, 16), /ink-muted|loss/);
  assert.match(getRankBadgeClass(1, 16), /accent/);
  assert.match(getRankBadgeClass(16, 16), /loss/);
});

test("buildMatchupStats is null with no rows and pairs each offense with the opposing defense", () => {
  assert.equal(buildMatchupStats([], 5, "A", "B"), null);
  const rows = [
    row("A", "offense", "epa_pass", 0.3, 5),
    row("B", "defense", "epa_pass", -0.1, 4),
    row("B", "offense", "epa_pass", 0.2, 9),
    row("A", "defense", "epa_pass", 0.4, 100),
  ];
  const stats = buildMatchupStats(rows, 5, "A", "B");
  assert.equal(stats?.asOfWeek, 5);
  assert.equal(stats?.awayOffVsHomeDef.find((r) => r.key === "epa_pass")?.defenseRank, 4);
  assert.equal(stats?.homeOffVsAwayDef.find((r) => r.key === "epa_pass")?.defenseRank, 100);
  assert.equal(stats?.cohortSize, 130);
});

test("metrics are grouped into three sections in display order", () => {
  const groups = groupUnitRows(buildUnitRows([], "A", "B"));
  assert.deepEqual(groups.map((g) => g.section), ["possession", "situational", "drive"]);
  assert.deepEqual(groups.map((g) => g.label), [
    SECTION_LABELS.possession,
    SECTION_LABELS.situational,
    SECTION_LABELS.drive,
  ]);
  assert.deepEqual(groups.map((g) => g.rows.length), [5, 6, 3]);
  assert.equal(groups.flatMap((g) => g.rows).length, UNIT_METRICS.length);
  assert.equal(new Set(UNIT_METRICS.map((m) => m.key)).size, UNIT_METRICS.length);
});

test("possession metrics format and pair like the others", () => {
  const rows = [
    row("A", "offense", "ppp", 2.456, 10),
    row("B", "defense", "ppp", 1.9, 25),
    row("A", "offense", "plays_per_possession", 5.857, 3),
    row("B", "defense", "non_offense_points_per_game", 3.5, 90),
    row("A", "offense", "epa_per_possession", -0.25, 70),
  ];
  const out = Object.fromEntries(buildUnitRows(rows, "A", "B").map((r) => [r.key, r]));
  assert.deepEqual([out.ppp.offenseValue, out.ppp.defenseValue], ["2.46", "1.90"]);
  assert.equal(out.plays_per_possession.offenseValue, "5.9");
  assert.equal(out.non_offense_points_per_game.defenseValue, "3.5");
  assert.equal(out.epa_per_possession.offenseValue, "−0.25");
});

test("matchup reads only raw possession stats: the adjusted table is never queried", () => {
  for (const file of ["queries.ts", "matchup.ts"]) {
    const source = readFileSync(new URL(`./${file}`, import.meta.url), "utf8");
    assert.doesNotMatch(source, /teamPossessionAdjusted|team_possession_adjusted/);
  }
  const queries = readFileSync(new URL("./queries.ts", import.meta.url), "utf8");
  assert.match(queries, /schema\.teamPossessionStats/);
  assert.doesNotMatch(queries, /adjustedValue|opponentAdjustment/);
});
