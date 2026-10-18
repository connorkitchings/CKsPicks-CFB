import assert from "node:assert/strict";
import test from "node:test";
import {
  ADJUSTED_CONFIG,
  CHART_REGISTRY,
  chartHref,
  chartSubtitle,
  describeAdjustedPoint,
  efficiencyConfig,
  exportFilename,
  formatEpaTick,
  parseChartKind,
  parseEfficiencyMetric,
  parseTeamParam,
  pickerGroups,
  withTeamParam,
} from "./chart-config.ts";
import type { AdjustedRow, ChartKind } from "./charts.ts";

const roster = [
  { team: "Alabama", conference: "SEC" },
  { team: "Notre Dame", conference: null },
  { team: "Texas A&M", conference: "SEC" },
];

test("team param: a roster team in any case is returned in roster spelling; anything else is ignored", () => {
  assert.equal(parseTeamParam("Alabama", roster), "Alabama");
  assert.equal(parseTeamParam("  notre dame ", roster), "Notre Dame");
  assert.equal(parseTeamParam("Texas A&M", roster), "Texas A&M");
  assert.equal(parseTeamParam("Alabam", roster), null, "no partial matches");
  assert.equal(parseTeamParam("Wyoming", roster), null, "unknown team");
  assert.equal(parseTeamParam("", roster), null);
  assert.equal(parseTeamParam("   ", roster), null);
  assert.equal(parseTeamParam(undefined, roster), null);
  assert.equal(parseTeamParam(null, roster), null);
  assert.equal(parseTeamParam(["Alabama", "Notre Dame"], roster), null, "a repeated param is ambiguous");
  assert.equal(parseTeamParam("Alabama", []), null);
});

test("chart hrefs write only the params a chart reads, and always carry the team", () => {
  assert.equal(chartHref("net-success", { side: "defense", week: 3 }), "/charts?chart=net-success&week=3");
  assert.equal(chartHref("efficiency", { side: "defense", week: 3, team: "Texas A&M" }), "/charts?chart=efficiency&side=defense&week=3&team=Texas+A%26M");
  assert.equal(chartHref("efficiency"), "/charts?chart=efficiency&side=offense");
  assert.equal(chartHref("adjusted", { side: "defense", week: null }), "/charts?chart=adjusted");
  assert.equal(chartHref("net-success", { week: 0, team: "Alabama" }), "/charts?chart=net-success&week=0&team=Alabama");
  assert.equal(chartHref("trajectory", { week: 4, team: "Alabama" }), "/charts?chart=trajectory&team=Alabama", "no week selector, no week param");
});

test("team param editing keeps every other param", () => {
  assert.equal(withTeamParam("/charts?chart=adjusted&week=2", "Notre Dame"), "/charts?chart=adjusted&week=2&team=Notre+Dame");
  assert.equal(withTeamParam("/charts?chart=adjusted&team=Alabama&week=2", "Notre Dame"), "/charts?chart=adjusted&team=Notre+Dame&week=2");
  assert.equal(withTeamParam("/charts?team=Alabama&week=2", null), "/charts?week=2");
  assert.equal(withTeamParam("/charts?team=Alabama", null), "/charts");
  assert.equal(withTeamParam("/charts", null), "/charts");
});

test("registry: every kind is registered; only ready kinds parse and appear in the picker", () => {
  const kinds: ChartKind[] = ["net-success", "efficiency", "adjusted", "schedule", "trajectory", "game-log"];
  assert.deepEqual(Object.keys(CHART_REGISTRY).sort(), [...kinds].sort());
  assert.deepEqual(kinds.map((kind) => CHART_REGISTRY[kind].group), ["games", "teams", "teams", "teams", "teams", "one-team"]);
  assert.equal(parseChartKind("adjusted"), "adjusted");
  assert.equal(parseChartKind("bogus"), "net-success");
  assert.equal(parseChartKind(undefined), "net-success");
  assert.equal(parseChartKind(["efficiency"]), "net-success");
  for (const kind of kinds.filter((k) => !CHART_REGISTRY[k].ready)) assert.equal(parseChartKind(kind), "net-success", kind);
  const groups = pickerGroups();
  assert.ok(groups.every((group) => group.kinds.length > 0 && group.kinds.every((kind) => CHART_REGISTRY[kind].ready)));
  assert.deepEqual(groups.flatMap((group) => group.kinds), kinds.filter((kind) => CHART_REGISTRY[kind].ready));
  assert.equal(groups[0].label, "Games");
});

test("titles, subtitles and export names follow the registry", () => {
  assert.equal(CHART_REGISTRY["net-success"].title, "Did We Really Get Beat That Bad?");
  assert.equal(CHART_REGISTRY.efficiency.title, "Efficiency vs Explosiveness");
  assert.equal(chartSubtitle("efficiency", 2026, 7, "offense"), "Offense | 2026 | FBS vs FBS | Through Week 7");
  assert.equal(chartSubtitle("adjusted", 2026, 3, "defense"), "2026 | FBS vs FBS | Through Week 3");
  assert.equal(chartSubtitle("net-success", 2026, 0, "offense"), "Week 0 | 2026 | FBS vs FBS");
  assert.equal(chartSubtitle("trajectory", 2026, 5, "offense"), "2026 | FBS vs FBS");
  assert.equal(exportFilename("efficiency", 2026, 3, "defense"), "ckspicks-efficiency-defense-2026-through-week-3.png");
  assert.equal(exportFilename("net-success", 2026, 0, "offense"), "ckspicks-net-success-2026-week-0.png");
  assert.equal(exportFilename("adjusted", 2026, 3, "offense"), "ckspicks-adjusted-2026-through-week-3.png");
});

test("efficiency axes follow side and metric; explosiveness defaults to 20+ rate only when served", () => {
  const defense = efficiencyConfig("defense", "explosive_rate");
  assert.equal(defense.yLabel, "20+ Yard Play Rate Allowed");
  assert.equal(defense.captions.topRight, "Lower allowed success / Lower allowed 20+ rate");
  assert.match(defense.footnote, /20\+ yard play rate/);
  assert.equal(efficiencyConfig("offense", "ppa").captions.bottomRight, "Higher success / Lower PPA");
  assert.equal(efficiencyConfig("offense", "yards_per_success").tickY(11.6), "12 yds");
  assert.deepEqual([0.07, 0.075, 0.08, 0.4].map(efficiencyConfig("offense", "explosive_rate").tickY), ["7%", "7.5%", "8%", "40%"], "half-percent ticks stay distinct");
  assert.equal(parseEfficiencyMetric(undefined, true), "explosive_rate");
  assert.equal(parseEfficiencyMetric("yards-per-success", true), "yards_per_success");
  assert.equal(parseEfficiencyMetric("yards_per_success", false), "ppa");
});

test("adjusted ticks use two decimals and the tooltip shows the stored decomposition", () => {
  assert.equal(ADJUSTED_CONFIG.tickX(0.1), "+0.10");
  assert.deepEqual([formatEpaTick(-0.05), formatEpaTick(0), formatEpaTick(-0.001)], ["-0.05", "0.00", "0.00"]);
  const role = (r: "offense" | "defense", adjusted: number, rank: number): AdjustedRow => ({
    asOfWeek: 4, team: "Alabama", role: r, rawEpaPerPlay: adjusted + 0.03, venueCorrection: 0.01, opponentAdjustment: 0.02,
    adjustedEpaPerPlay: adjusted, epaN: 100, games: 3, adjustedRank: rank, cohortSize: 134,
  });
  const point = { team: "Alabama", conference: "SEC", x: 0.2, y: -0.1, n: 200 };
  const text = describeAdjustedPoint(point, { Alabama: { offense: role("offense", 0.2, 5), defense: role("defense", -0.1, 12) } });
  assert.equal(
    text,
    "Alabama (SEC): offense adjusted +0.200 (raw +0.230, venue correction +0.010, opponent adjustment +0.020), rank 5 of 134; " +
      "defense allowed adjusted -0.100 (raw -0.070, venue correction +0.010, opponent adjustment +0.020), rank 12 of 134 PPA/play",
  );
  assert.equal(describeAdjustedPoint(point, {}), "Alabama (SEC): adjusted offense +0.200, adjusted defense allowed -0.100 PPA/play");
});
