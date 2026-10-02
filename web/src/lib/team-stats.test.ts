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
  rankLabel,
  rankTitle,
  rankTier,
  rowEdge,
  rowGap,
  edgeSummary,
  mismatchSentence,
  topMismatches,
  SECTION_LABELS,
  UNIT_METRICS,
  type TeamStatRow,
  type UnitMatchupRow,
} from "./team-stats.ts";

const row = (
  team: string,
  role: "offense" | "defense",
  metric: string,
  value: number | null,
  rank: number | null,
  tied = false,
): TeamStatRow => ({
  team, role, metric, value, n: 10, games: 4, rank, cohortSize: rank === null ? null : 130, tied,
});

test("formatMetric formats each kind and shows a dash for missing values", () => {
  assert.equal(formatMetric("epa", 0.234), "+0.23");
  assert.equal(formatMetric("epa", -0.05), "−0.05");
  assert.equal(formatMetric("pct", 0.4567), "45.7%");
  assert.equal(formatMetric("pts", 4.1), "4.10");
  assert.equal(formatMetric("field", 31.25), "Own 31.3");
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
  assert.equal(out.length, 12);
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
  assert.deepEqual(groups.map((g) => g.rows.length), [3, 6, 3]);
  assert.equal(groups.flatMap((g) => g.rows).length, UNIT_METRICS.length);
  assert.equal(new Set(UNIT_METRICS.map((m) => m.key)).size, UNIT_METRICS.length);
});

test("possession metrics format and pair like the others", () => {
  const rows = [
    row("A", "offense", "ppp", 2.456, 10),
    row("B", "defense", "ppp", 1.9, 25),
    row("A", "offense", "epa_per_possession", -0.25, 70),
  ];
  const out = Object.fromEntries(buildUnitRows(rows, "A", "B").map((r) => [r.key, r]));
  assert.deepEqual([out.ppp.offenseValue, out.ppp.defenseValue], ["2.46", "1.90"]);
  assert.equal(out.epa_per_possession.offenseValue, "−0.25");
});

test("plays per possession and non-offense points are stored but not shown on the matchup", () => {
  const keys = UNIT_METRICS.map((m) => m.key);
  assert.ok(!keys.includes("plays_per_possession"));
  assert.ok(!keys.includes("non_offense_points_per_game"));
  // PPA/play is read from team stats (punt plays excluded), not the V5 epa_per_play companion.
  assert.ok(keys.includes("ppa_per_play"));
  assert.ok(!keys.includes("epa_per_play"));
});

test("rankLabel and rankTitle show ties as T-N and unranked as a dash", () => {
  assert.equal(rankLabel(75, false), "#75");
  assert.equal(rankLabel(75, true), "T-75");
  assert.equal(rankLabel(null, false), "—");
  assert.equal(rankLabel(null, true), "—");
  assert.equal(rankTitle(75, true, 138), "Tied for #75 of 138");
  assert.equal(rankTitle(75, false, 138), "National rank #75 of 138");
  assert.equal(rankTitle(null, false, null), "Not ranked");
});

test("ties carry through to the row and an exact zero is unranked", () => {
  const rows = [
    row("A", "offense", "ppp", 2.0, 40, true),
    row("B", "defense", "ppp", 1.5, 40, false),
    row("A", "offense", "explosive_rate", 0, 74, true), // zero: value shown, no rank, no tie
    row("B", "defense", "explosive_rate", 0.06, 20),
  ];
  const out = Object.fromEntries(buildUnitRows(rows, "A", "B").map((r) => [r.key, r]));
  assert.deepEqual([out.ppp.offenseRank, out.ppp.offenseTied, out.ppp.defenseTied], [40, true, false]);
  assert.equal(out.explosive_rate.offenseValue, "0.0%");
  assert.deepEqual(
    [out.explosive_rate.offenseRank, out.explosive_rate.offenseCohort, out.explosive_rate.offenseTied],
    [null, null, false],
  );
  assert.equal(out.explosive_rate.edge, null); // an unranked side gives no edge cue
});

test("rowEdge compares the offense rank with the opposing defense rank", () => {
  // Cohort of 101: percentile = 1 - (rank - 1) / 100.
  assert.deepEqual(rowEdge(11, 101, 61, 101), { side: "offense", strength: "strong" }); // gap 0.50
  assert.deepEqual(rowEdge(61, 101, 11, 101), { side: "defense", strength: "strong" });
  assert.deepEqual(rowEdge(41, 101, 61, 101), { side: "offense", strength: "slight" }); // gap 0.20
  assert.deepEqual(rowEdge(61, 101, 41, 101), { side: "defense", strength: "slight" });
  assert.deepEqual(rowEdge(50, 101, 55, 101), { side: "even", strength: null }); // gap 0.05
  assert.deepEqual(rowEdge(21, 101, 51, 101), { side: "offense", strength: "strong" }); // exactly 0.30
  assert.equal(rowEdge(null, 101, 50, 101), null);
  assert.equal(rowEdge(50, 101, null, 101), null);
  // Different cohort sizes compare by percentile, not raw rank.
  assert.deepEqual(rowEdge(3, 16, 120, 138), { side: "offense", strength: "strong" });
});

test("edgeSummary counts each side and ignores rows that cannot be compared", () => {
  const rows = buildUnitRows(
    [
      row("A", "offense", "ppp", 3, 5),
      row("B", "defense", "ppp", 2, 100),
      row("A", "offense", "epa_rush", 0.1, 100),
      row("B", "defense", "epa_rush", 0.05, 5),
      row("A", "offense", "success_rate", 0.4, 60),
      row("B", "defense", "success_rate", 0.4, 62),
      row("A", "offense", "epa_pass", 0.2, null),
    ],
    "A",
    "B",
  );
  assert.deepEqual(edgeSummary(rows), { offense: 1, defense: 1, even: 1 });
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

const unitRow = (
  name: string,
  offenseRank: number | null,
  defenseRank: number | null,
  offenseTied = false,
): UnitMatchupRow => ({
  key: name,
  name,
  offenseValue: "0",
  offenseRank,
  offenseCohort: offenseRank === null ? null : 100,
  offenseTied,
  defenseValue: "0",
  defenseRank,
  defenseCohort: defenseRank === null ? null : 100,
  defenseTied: false,
  edge: null,
  section: "possession",
});

test("rowGap is positive when the offense outranks the defense and null when either side is unranked", () => {
  assert.equal(rowGap(1, 100, 100, 100), 1);
  assert.equal(rowGap(100, 100, 1, 100), -1);
  assert.equal(rowGap(50, 100, 50, 100), 0);
  assert.equal(rowGap(null, null, 5, 100), null);
  assert.equal(rowGap(5, 100, null, null), null);
});

test("topMismatches ranks the biggest gaps first across both panels and skips even and unranked rows", () => {
  const panels = [
    {
      offenseTeam: "A",
      defenseTeam: "B",
      rows: [unitRow("PPA/play", 10, 90), unitRow("Success rate", 50, 52), unitRow("Explosive", null, 5)],
    },
    { offenseTeam: "B", defenseTeam: "A", rows: [unitRow("PPA/play", 95, 4), unitRow("Pts/scoring opp", 20, 60)] },
  ];
  const top = topMismatches(panels);
  // Percentile gaps (cohort 100): B offense #95 vs A defense #4 = 0.92 (A defense);
  // A offense #10 vs B defense #90 = 0.81 (A offense); B offense #20 vs A defense #60 = 0.40 (B offense).
  assert.deepEqual(
    top.map((m) => [m.metric, m.favoredTeam, m.favoredUnit]),
    [
      ["PPA/play", "A", "defense"],
      ["PPA/play", "A", "offense"],
      ["Pts/scoring opp", "B", "offense"],
    ],
  );
  assert.equal(topMismatches(panels, 1).length, 1);
  assert.ok(top.every((m) => m.gap >= 0.1), "rows inside the even band are skipped");
});

test("topMismatches keeps display order for equal gaps and returns fewer than requested when rows are even", () => {
  const even = [{ offenseTeam: "A", defenseTeam: "B", rows: [unitRow("x", 40, 42)] }];
  assert.deepEqual(topMismatches(even), []);
  const tie = [
    { offenseTeam: "A", defenseTeam: "B", rows: [unitRow("first", 10, 90), unitRow("second", 10, 90)] },
  ];
  assert.deepEqual(topMismatches(tie).map((m) => m.metric), ["first", "second"]);
});

test("mismatchSentence names both units with their ranks, T- for ties", () => {
  const [m] = topMismatches([
    { offenseTeam: "Western Kentucky", defenseTeam: "New Mexico State", rows: [unitRow("PPA/play", 12, 131, true)] },
  ]);
  assert.equal(
    mismatchSentence(m),
    "Western Kentucky offense T-12 vs New Mexico State defense #131: PPA/play",
  );
});

test("rankTier uses the same percentile bands as the badge classes", () => {
  assert.equal(rankTier(null), "none");
  assert.equal(rankTier(27, 138), "top"); // 19.6%
  assert.equal(rankTier(28, 138), "high");
  assert.equal(rankTier(62, 138), "high"); // 44.9%
  assert.equal(rankTier(63, 138), "mid");
  assert.equal(rankTier(103, 138), "mid"); // 74.6%
  assert.equal(rankTier(104, 138), "low");
  assert.match(getRankBadgeClass(1, 138), /accent/);
  assert.match(getRankBadgeClass(138, 138), /loss/);
});
