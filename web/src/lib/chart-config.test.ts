import assert from "node:assert/strict";
import test from "node:test";
import {
  EFFICIENCY_METRICS,
  gameLogFootnote,
  footnoteLines,
  SUCCESS_RATE_DEFINITION,
  ADJUSTED_CONFIG,
  CHART_REGISTRY,
  chartHref,
  chartSubtitle,
  describeAdjustedPoint,
  describeDownsPoint,
  describeFinishingDrivesPoint,
  describeResumePoint,
  downsConfig,
  efficiencyConfig,
  exportFilename,
  finishingDrivesConfig,
  formatEpaTick,
  parseChartKind,
  parseEfficiencyMetric,
  parseMarketBoardMetric,
  parseTeamParam,
  pickerGroups,
  readyKinds,
  RESUME_QUALITY_CONFIG,
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
  assert.equal(chartHref("net-success", { side: "defense", week: 3 }), "/stats?chart=net-success&week=3");
  assert.equal(chartHref("efficiency", { side: "defense", week: 3, team: "Texas A&M" }), "/stats?chart=efficiency&side=defense&week=3&team=Texas+A%26M");
  assert.equal(chartHref("efficiency"), "/stats?chart=efficiency&side=offense");
  assert.equal(chartHref("adjusted", { side: "defense", week: null }), "/stats?chart=adjusted");
  assert.equal(chartHref("net-success", { week: 0, team: "Alabama" }), "/stats?chart=net-success&week=0&team=Alabama");
  assert.equal(chartHref("rating-trajectory", { side: "defense", week: 4, team: "Alabama" }), "/stats?chart=rating-trajectory&team=Alabama");
  assert.equal(chartHref("possession", { side: "defense", week: 2, team: "Alabama" }), "/stats?chart=possession&week=2&team=Alabama", "Through Week N, no side");
});

test("team param editing keeps every other param", () => {
  assert.equal(withTeamParam("/stats?chart=adjusted&week=2", "Notre Dame"), "/stats?chart=adjusted&week=2&team=Notre+Dame");
  assert.equal(withTeamParam("/stats?chart=adjusted&team=Alabama&week=2", "Notre Dame"), "/stats?chart=adjusted&team=Notre+Dame&week=2");
  assert.equal(withTeamParam("/stats?team=Alabama&week=2", null), "/stats?week=2");
  assert.equal(withTeamParam("/stats?team=Alabama", null), "/stats");
  assert.equal(withTeamParam("/stats", null), "/stats");
});

test("registry: every kind is registered; only ready kinds parse and appear in the picker", () => {
  const kinds: ChartKind[] = [
    "net-success",
    "market-board",
    "efficiency",
    "adjusted",
    "rating-trajectory",
    "possession",
    "downs",
    "finishing-drives",
    "resume-quality",
    "game-log",
  ];
  assert.deepEqual(Object.keys(CHART_REGISTRY).sort(), [...kinds].sort());
  assert.deepEqual(
    kinds.map((kind) => CHART_REGISTRY[kind].group),
    ["games", "games", "teams", "teams", "teams", "teams", "teams", "teams", "teams", "one-team"],
  );
  assert.equal(parseChartKind("adjusted"), "adjusted");
  assert.equal(parseChartKind("possession"), "possession");
  assert.equal(parseChartKind("game-log"), "game-log");
  assert.equal(parseChartKind("downs"), "downs");
  assert.equal(parseChartKind("finishing-drives"), "finishing-drives");
  // Hidden from public picker: rating-trajectory, market-board, and resume-quality (retained for research/internal).
  assert.equal(CHART_REGISTRY["rating-trajectory"].ready, false);
  assert.equal(parseChartKind("rating-trajectory"), "net-success");
  assert.equal(CHART_REGISTRY["market-board"].ready, false);
  assert.equal(parseChartKind("market-board"), "net-success");
  assert.equal(CHART_REGISTRY["resume-quality"].ready, false);
  assert.equal(parseChartKind("resume-quality"), "net-success");
  // Removed kinds fall back to the default chart like any unknown name.
  for (const removed of ["schedule", "trajectory"]) assert.equal(parseChartKind(removed), "net-success", removed);
  assert.deepEqual(pickerGroups().flatMap((group) => group.kinds.map((kind) => CHART_REGISTRY[kind].tabLabel)), [
    "Net success rate",
    "Efficiency vs explosiveness",
    "Adjusted PPA/play",
    "Possession efficiency",
    "Situational downs",
    "Finishing drives",
    "Game log",
  ]);
  assert.equal(parseChartKind("bogus"), "net-success");
  assert.equal(parseChartKind(undefined), "net-success");
  assert.equal(parseChartKind(["efficiency"]), "net-success");
  for (const kind of kinds.filter((k) => !CHART_REGISTRY[k].ready)) assert.equal(parseChartKind(kind), "net-success", kind);
  const groups = pickerGroups();
  assert.ok(groups.every((group) => group.kinds.length > 0 && group.kinds.every((kind) => CHART_REGISTRY[kind].ready)));
  assert.equal(groups[0].label, "Games");
});

test("titles, subtitles and export names follow the registry", () => {
  assert.equal(CHART_REGISTRY["net-success"].title, "Net success rate");
  assert.equal(CHART_REGISTRY["net-success"].credit, "Inspired by Parker Fleming: “Did We Really Get Beat That Bad?”");
  assert.equal(CHART_REGISTRY.efficiency.title, "Efficiency vs explosiveness");
  // Titles match their picker tabs, in sentence case, and each visible chart has a one-sentence description.
  for (const kind of readyKinds()) {
    assert.equal(CHART_REGISTRY[kind].title, CHART_REGISTRY[kind].tabLabel);
    assert.match(CHART_REGISTRY[kind].description, /^[A-Z].*\.$/);
  }
  assert.equal(chartSubtitle("efficiency", 2026, 7, "offense"), "Offense | 2026 | FBS vs FBS | Through Week 7");
  assert.equal(chartSubtitle("adjusted", 2026, 3, "defense"), "2026 | FBS vs FBS | Through Week 3");
  assert.equal(chartSubtitle("net-success", 2026, 0, "offense"), "Week 0 | 2026 | FBS vs FBS");
  assert.equal(exportFilename("efficiency", 2026, 3, "defense"), "stratum-efficiency-defense-2026-through-week-3.png");
  assert.equal(exportFilename("net-success", 2026, 0, "offense"), "stratum-net-success-2026-week-0.png");
  assert.equal(exportFilename("adjusted", 2026, 3, "offense"), "stratum-adjusted-2026-through-week-3.png");
  // V5 ratings and possession measurements are FBS teams' values from every game, not an FBS-vs-FBS game filter.
  assert.equal(chartSubtitle("possession", 2026, 2, "defense"), "2026 | FBS teams, all games | Through Week 2");
  assert.equal(chartSubtitle("rating-trajectory", 2026, 7, "defense"), "2026 | FBS teams");
  assert.equal(exportFilename("possession", 2026, 2, "defense", "ppp"), "stratum-possession-ppp-2026-through-week-2.png");
  assert.equal(exportFilename("rating-trajectory", 2026, 7, "offense", "overall"), "stratum-rating-trajectory-overall-2026.png");
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

test("footnotes split into one line per sentence and no longer carry the release note", () => {
  for (const kind of Object.keys(CHART_REGISTRY) as (keyof typeof CHART_REGISTRY)[]) {
    const { footnote } = CHART_REGISTRY[kind];
    assert.ok(!footnote.includes("Reconstructed from"), `${kind} footnote`);
    assert.ok(footnoteLines(footnote).every((line) => /[.!?]$/.test(line)), `${kind} lines end a sentence`);
  }
  assert.deepEqual(footnoteLines(CHART_REGISTRY["net-success"].footnote), [
    "Bar = winner's offensive success-rate advantage/disadvantage in percentage points, on eligible plays (regulation only; garbage time and special teams excluded).",
    "Label = winner and final score.",
    SUCCESS_RATE_DEFINITION,
  ]);
});

test("footnotes carry the metric definitions and the subtitles stay one sentence", () => {
  for (const metric of ["ppa", "explosive_rate", "yards_per_success"] as const) {
    const lines = footnoteLines(efficiencyConfig("offense", metric).footnote);
    assert.ok(lines.includes(SUCCESS_RATE_DEFINITION), `${metric} defines success rate`);
    assert.ok(lines.includes(EFFICIENCY_METRICS[metric].definition), `${metric} defines its metric`);
  }
  assert.match(efficiencyConfig("offense", "explosive_rate").footnote, /20 or more yards/);
  assert.ok(footnoteLines(CHART_REGISTRY["net-success"].footnote).includes(SUCCESS_RATE_DEFINITION));
  assert.equal(footnoteLines(CHART_REGISTRY.efficiency.description).length, 1);
  assert.equal(footnoteLines(CHART_REGISTRY["net-success"].description).length, 1);
});

test("the game log footnote defines the selected metric and leaves scope notes to the chart", () => {
  assert.ok(footnoteLines(gameLogFootnote("success")).includes(SUCCESS_RATE_DEFINITION));
  assert.ok(footnoteLines(gameLogFootnote("ppa")).includes(EFFICIENCY_METRICS.ppa.definition));
  assert.ok(footnoteLines(gameLogFootnote("explosive_rate")).includes(EFFICIENCY_METRICS.explosive_rate.definition));
  for (const metric of ["success", "ppa", "explosive_rate"] as const) {
    assert.ok(!gameLogFootnote(metric).includes("FBS opponents only"), metric);
    assert.ok(!gameLogFootnote(metric).includes("axis inverted"), metric);
  }
  assert.equal(CHART_REGISTRY["game-log"].footnote, gameLogFootnote("success"));
});

test("downs and finishing drives quadrant names match their positions on both sides", () => {
  // Defense axes are inverted: up = fewer allowed on y, right = fewer allowed on x.
  const expected = {
    downs: {
      offense: ["Late-Down Bailouts", "Unstoppable Engine", "Struggling", "On-Schedule Only"],
      defense: ["Bend, Don't Break", "Suffocating Defense", "Vulnerable", "Stingy Early, Leaky Late"],
    },
    finishing: {
      offense: ["Low Volume, High TD Rate", "Elite Finishers", "Struggling Finishers", "Drive Stallers / FG Settlers"],
      defense: ["Red-Zone Wall", "Lockdown Defense", "Generous Defense", "Stingy Early, Leaky Inside"],
    },
  };
  for (const side of ["offense", "defense"] as const) {
    for (const [config, names] of [
      [downsConfig(side), expected.downs[side]],
      [finishingDrivesConfig(side), expected.finishing[side]],
    ] as const) {
      const n = config.captions.names;
      assert.deepEqual([n.topLeft, n.topRight, n.bottomLeft, n.bottomRight], names, side);
    }
  }

  const downsDefCaptions = downsConfig("defense").captions;
  assert.equal(downsDefCaptions.topLeft, "Higher early EPA allowed / Lower conversion allowed");
  assert.equal(downsDefCaptions.bottomRight, "Lower early EPA allowed / Higher conversion allowed");
  const finishingDefCaptions = finishingDrivesConfig("defense").captions;
  assert.equal(finishingDefCaptions.topLeft, "Higher opportunity rate allowed / Fewer points allowed per opportunity");
  assert.equal(finishingDefCaptions.bottomRight, "Lower opportunity rate allowed / More points allowed per opportunity");
  const downsOffCaptions = downsConfig("offense").captions;
  assert.equal(downsOffCaptions.topLeft, "Lower early EPA / Higher conversion");
  assert.equal(downsOffCaptions.bottomRight, "Higher early EPA / Lower conversion");
  const finishingOffCaptions = finishingDrivesConfig("offense").captions;
  assert.equal(finishingOffCaptions.topLeft, "Lower opportunity rate / Higher points per opportunity");
  assert.equal(finishingOffCaptions.bottomRight, "Higher opportunity rate / Lower points per opportunity");
});

test("footnotes: pooled finishing average and cohort-neutral resume rank", () => {
  assert.ok(finishingDrivesConfig("offense").footnote?.includes("pooled over drives for opportunity rate and over scoring opportunities"));
  assert.ok(downsConfig("offense").footnote?.includes("pooled over plays: early-down plays for EPA, 3rd/4th-down attempts for conversion rate."));
  assert.ok(!RESUME_QUALITY_CONFIG.footnote?.includes("134"));
  assert.equal(RESUME_QUALITY_CONFIG.averageNames.y, "Avg SOR rank");
});

test("advanced visualization suite configs and formatters", () => {
  const downsOff = downsConfig("offense");
  assert.equal(downsOff.xLabel, "Early Down PPA/play (1st & 2nd)");
  assert.equal(downsOff.captions.names.topRight, "Unstoppable Engine");
  assert.equal(downsOff.captions.names.bottomRight, "On-Schedule Only");

  const downsDef = downsConfig("defense");
  assert.equal(downsDef.captions.names.topRight, "Suffocating Defense");
  assert.equal(downsDef.captions.names.bottomRight, "Stingy Early, Leaky Late");

  const finishingOff = finishingDrivesConfig("offense");
  assert.equal(finishingOff.xLabel, "Scoring Opportunity Rate (Drives to Opponent 40)");
  assert.equal(finishingOff.yLabel, "Points per Scoring Opportunity");
  assert.equal(finishingOff.captions.names.topRight, "Elite Finishers");
  assert.equal(finishingOff.captions.names.bottomRight, "Drive Stallers / FG Settlers");

  const finishingDef = finishingDrivesConfig("defense");
  assert.equal(finishingDef.xLabel, "Scoring Opportunity Rate Allowed");
  assert.equal(finishingDef.yLabel, "Points Allowed per Scoring Opportunity");
  assert.equal(finishingDef.captions.names.topRight, "Lockdown Defense");

  assert.equal(RESUME_QUALITY_CONFIG.captions.names.topRight, "Championship Contenders");
  assert.equal(RESUME_QUALITY_CONFIG.captions.names.bottomRight, "Unlucky / Untested Giants");

  assert.equal(parseMarketBoardMetric("total"), "total");
  assert.equal(parseMarketBoardMetric("spread"), "spread");
  assert.equal(parseMarketBoardMetric(null), "spread");

  const pt = { team: "Georgia", conference: "SEC", x: 0.25, y: 45, n: 100 };
  assert.match(describeDownsPoint({ ...pt, y: 0.45 }, "offense"), /Georgia \(SEC\): Early-down EPA \+0.250, 3rd\/4th down conv 45.0%/);
  assert.match(describeFinishingDrivesPoint({ ...pt, x: 0.25, y: 4.5 }, "offense"), /Georgia \(SEC\): Scoring opportunity rate 25.0%, points per scoring opportunity 4.50/);
  assert.match(describeResumePoint(pt), /Georgia \(SEC\): V5 Rating \+0.25, Strength of Record #45/);
});
