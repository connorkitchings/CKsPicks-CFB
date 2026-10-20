import assert from "node:assert/strict";
import test from "node:test";
import {
  adjustedPoints,
  adjustedThroughWeeks,
  buildConferenceMap,
  chartColor,
  coerceWeek,
  conferenceOptions,
  domainFor,
  efficiencyPoints,
  efficiencyThroughWeeks,
  filterNetSuccessBars,
  scatterRanks,
  formatEpa,
  formatPercent,
  matchesConference,
  matchesSearch,
  matchesTeamConference,
  netSuccessBars,
  netSuccessWeeks,
  niceTicks,
  outplayedWinners,
  relativeLuminance,
  sortNetSuccessBars,
  withYardage,
  type AdjustedRow,
  type RosterRow,
  type TeamGameRow,
  type TeamGameYardageRow,
} from "./charts.ts";
import { teamAbbr, teamAltColor, teamColor, FALLBACK_TEAM_COLOR } from "./team-logos.ts";

function row(partial: Partial<TeamGameRow> & Pick<TeamGameRow, "gameId" | "team" | "opponent">): TeamGameRow {
  return {
    week: 0,
    site: "home",
    pointsFor: 20,
    pointsAgainst: 10,
    offPlays: 10,
    offSuccessN: 10,
    offSuccessSum: 5,
    offEpaN: 10,
    offEpaSum: 1,
    defPlays: 10,
    defSuccessN: 10,
    defSuccessSum: 5,
    defEpaN: 10,
    defEpaSum: 1,
    ...partial,
  };
}

/** Both mirrored rows of one game. */
function game(
  gameId: number,
  week: number,
  home: [string, number, number, number],
  away: [string, number, number, number],
): TeamGameRow[] {
  // [team, points, offense success n, offense success sum]
  const [h, hp, hn, hs] = home;
  const [a, ap, an, as] = away;
  return [
    row({ gameId, week, team: h, opponent: a, pointsFor: hp, pointsAgainst: ap, offSuccessN: hn, offSuccessSum: hs, defSuccessN: an, defSuccessSum: as }),
    row({ gameId, week, team: a, opponent: h, site: "away", pointsFor: ap, pointsAgainst: hp, offSuccessN: an, offSuccessSum: as, defSuccessN: hn, defSuccessSum: hs }),
  ];
}

const roster: RosterRow[] = [
  { team: "Alabama", conference: "SEC" },
  { team: "Michigan", conference: "Big Ten" },
  { team: "Notre Dame", conference: "FBS Independents" },
  { team: "Tulane", conference: "American Athletic" },
  { team: "Idle State", conference: "Sun Belt" },
];

test("net success bars: winner minus loser offensive success, mirrored label, stable sort", () => {
  const rows = [
    ...game(1, 3, ["Alabama", 31, 20, 12], ["Michigan", 10, 20, 6]), // +0.30
    ...game(2, 3, ["Tulane", 7, 10, 3], ["Notre Dame", 24, 10, 7]), // Notre Dame wins: +0.40
    ...game(3, 3, ["Alabama", 14, 10, 5], ["Tulane", 13, 10, 5]), // +0.00 (hairline)
    ...game(4, 4, ["Michigan", 3, 10, 1], ["Tulane", 0, 10, 0]), // other week
  ];
  const { bars, notCharted } = netSuccessBars(rows, 3);
  assert.deepEqual(notCharted, []);
  assert.deepEqual(bars.map((b) => b.gameId), [3, 1, 2]);
  assert.equal(bars[0].value, 0);
  assert.ok(Math.abs(bars[1].value - 0.3) < 1e-12);
  assert.equal(bars[2].winner, "Notre Dame");
  assert.equal(bars[2].loser, "Tulane");
  assert.equal(bars[1].label, `${teamAbbr("Alabama")} 31-10`);
  assert.equal(netSuccessBars(rows, 9).bars.length, 0);
});

test("net success: tied points and missing success rates are listed, not charted", () => {
  const rows = [
    ...game(1, 0, ["Alabama", 10, 10, 5], ["Michigan", 10, 10, 5]),
    ...game(2, 0, ["Tulane", 17, 0, 0], ["Notre Dame", 3, 10, 4]),
    ...game(3, 0, ["Alabama", 17, 10, 6], ["Notre Dame", 3, 10, 4]),
  ];
  const { bars, notCharted } = netSuccessBars(rows, 0);
  assert.deepEqual(bars.map((b) => b.gameId), [3]);
  assert.deepEqual(notCharted, [
    { gameId: 1, reason: "tied points" },
    { gameId: 2, reason: "success rate unavailable" },
  ]);
  assert.deepEqual(netSuccessBars([rows[0]], 0).notCharted, [{ gameId: 1, reason: "incomplete game rows" }]);
});

test("available weeks per chart and week coercion", () => {
  const rows = [...game(1, 0, ["Alabama", 7, 1, 1], ["Michigan", 3, 1, 1]), ...game(2, 3, ["Tulane", 7, 1, 1], ["Alabama", 3, 1, 1])];
  assert.deepEqual(netSuccessWeeks(rows), [0, 3]);
  assert.deepEqual(efficiencyThroughWeeks(rows), [2, 3]);
  assert.deepEqual(efficiencyThroughWeeks([]), []);
  assert.deepEqual(adjustedThroughWeeks([3, 4, 4, 2]), [2, 3]);
  assert.equal(coerceWeek(0, [2, 3, 4, 7]), 2, "net-success Week 0 → first scatter week");
  assert.equal(coerceWeek(1, [2, 3, 4, 7]), 2);
  assert.equal(coerceWeek(5, [2, 3, 4, 7]), 4, "5 is nearer 4 than 7");
  assert.equal(coerceWeek(6, [2, 3, 4, 7]), 7);
  assert.equal(coerceWeek(9, [2, 3, 4, 7]), 7);
  assert.equal(coerceWeek(3, [2, 3, 4, 7]), 3);
  assert.equal(coerceWeek(5, [4, 6]), 6, "a tie goes to the later week");
  assert.equal(coerceWeek(null, [2, 3, 4, 7]), 7);
  assert.equal(coerceWeek(Number.NaN, [2, 3]), 3);
  assert.equal(coerceWeek(3, []), null);
});

test("efficiency: window sums, pooled averages, unavailable teams, defense inversion", () => {
  const rows = [
    ...game(1, 0, ["Alabama", 30, 10, 6], ["Michigan", 10, 10, 4]),
    ...game(2, 1, ["Alabama", 30, 10, 8], ["Tulane", 10, 10, 2]),
    ...game(3, 5, ["Michigan", 30, 10, 10], ["Tulane", 10, 10, 10]), // after the window
  ];
  const offense = efficiencyPoints(roster, rows, 1, "offense");
  const alabama = offense.points.find((p) => p.team === "Alabama")!;
  assert.equal(alabama.x, 14 / 20);
  assert.equal(alabama.y, 2 / 20);
  assert.equal(alabama.n, 20);
  assert.deepEqual(offense.unavailable, ["Idle State", "Notre Dame"]);
  assert.ok(offense.average && Math.abs(offense.average.x - (14 + 4 + 2) / 40) < 1e-12);
  assert.deepEqual([offense.invertX, offense.invertY], [false, false]);
  const defense = efficiencyPoints(roster, rows, 1, "defense");
  const michiganDefense = defense.points.find((p) => p.team === "Michigan")!;
  assert.equal(michiganDefense.x, 6 / 10, "defense allowed = opponent offense");
  assert.deepEqual([defense.invertX, defense.invertY], [true, true]);
  assert.deepEqual(efficiencyPoints(roster, rows, 1, "offense").points.map((p) => p.team), ["Alabama", "Michigan", "Tulane"]);
});

test("efficiency: a team with no valid success or EPA observation is unavailable, never zero", () => {
  const rows = [row({ gameId: 1, team: "Alabama", opponent: "Michigan", offSuccessN: 0, offSuccessSum: 0 })];
  const data = efficiencyPoints(roster, rows, 3, "offense");
  assert.equal(data.points.length, 0);
  assert.ok(data.unavailable.includes("Alabama"));
  assert.equal(data.average, null);
});

function adjusted(team: string, role: "offense" | "defense", value: number, epaN = 100): AdjustedRow {
  return {
    asOfWeek: 4,
    team,
    role,
    rawEpaPerPlay: value,
    venueCorrection: 0,
    opponentAdjustment: 0,
    adjustedEpaPerPlay: value,
    epaN,
    games: 3,
    adjustedRank: 1,
    cohortSize: 4,
  };
}

test("adjusted points need both roles; a one-role team is listed as unavailable", () => {
  const rows = [
    adjusted("Alabama", "offense", 0.2, 100),
    adjusted("Alabama", "defense", -0.1, 100),
    adjusted("Michigan", "offense", 0.0, 300),
    adjusted("Michigan", "defense", 0.1, 300),
    adjusted("Tulane", "offense", 0.3), // no defense row
    adjusted("Notre Dame", "defense", 0.05), // no offense row
  ];
  const data = adjustedPoints(roster, rows);
  assert.deepEqual(data.points.map((p) => p.team), ["Alabama", "Michigan"]);
  assert.deepEqual(data.unavailable, ["Idle State", "Notre Dame", "Tulane"]);
  assert.ok(data.average && Math.abs(data.average.x - (0.2 * 100 + 0 * 300) / 400) < 1e-12);
  assert.ok(data.average && Math.abs(data.average.y - (-0.1 * 100 + 0.1 * 300) / 400) < 1e-12);
  assert.deepEqual([data.invertX, data.invertY], [false, true]);
  assert.deepEqual(Object.keys(data.roles), ["Alabama", "Michigan"], "the decomposition covers plotted teams only");
  assert.equal(data.roles.Alabama.defense, rows[1]);
});

test("net success: winners-outplayed summary counts strictly lower winner success rates", () => {
  const { bars } = netSuccessBars([
    ...game(1, 3, ["Alabama", 31, 20, 12], ["Michigan", 10, 20, 6]), // +0.30
    ...game(2, 3, ["Tulane", 28, 10, 3], ["Notre Dame", 24, 10, 7]), // Tulane wins, -0.40
    ...game(3, 3, ["Michigan", 14, 10, 5], ["Notre Dame", 13, 10, 5]), // 0.00 is not outplayed
  ], 3);
  assert.deepEqual(outplayedWinners(bars), { outplayed: 1, total: 3 });
  assert.deepEqual(outplayedWinners([]), { outplayed: 0, total: 0 });
});

test("net success: margin sort orders by final margin with ties by game id; gap sort is the default order", () => {
  const { bars } = netSuccessBars([
    ...game(7, 3, ["Alabama", 11, 20, 12], ["Michigan", 10, 20, 6]), // margin 1, +0.30
    ...game(2, 3, ["Tulane", 17, 10, 3], ["Notre Dame", 14, 10, 7]), // margin 3, -0.40
    ...game(5, 3, ["Michigan", 24, 10, 6], ["Notre Dame", 21, 10, 5]), // margin 3, +0.10
    ...game(4, 3, ["Alabama", 45, 10, 9], ["Tulane", 0, 10, 1]), // margin 45, +0.80
  ], 3);
  assert.deepEqual(bars.map((b) => b.gameId), [2, 5, 7, 4]);
  assert.deepEqual(sortNetSuccessBars(bars, "margin").map((b) => b.gameId), [7, 2, 5, 4]);
  assert.deepEqual(sortNetSuccessBars([...bars].reverse(), "margin").map((b) => b.gameId), [7, 2, 5, 4], "the margin-3 tie falls back to game id, whatever the input order");
  assert.deepEqual(sortNetSuccessBars([...bars].reverse(), "gap").map((b) => b.gameId), [2, 5, 7, 4]);
  assert.deepEqual(bars.map((b) => b.gameId), [2, 5, 7, 4], "sorting copies; the input order is untouched");
});

test("conference filters come from the roster; Power Four adds Notre Dame", () => {
  assert.deepEqual(conferenceOptions(roster), ["American Athletic", "Big Ten", "FBS Independents", "SEC", "Sun Belt"]);
  const keep = (filter: string) => roster.filter((r) => matchesConference(filter, r.team, r.conference)).map((r) => r.team);
  assert.deepEqual(keep("all").length, 5);
  assert.deepEqual(keep("p4"), ["Alabama", "Michigan", "Notre Dame"]);
  assert.deepEqual(keep("SEC"), ["Alabama"]);
});

test("search matches names and abbreviations case-insensitively", () => {
  assert.equal(matchesSearch("", "Alabama"), false);
  assert.equal(matchesSearch("bama", "Alabama"), true);
  assert.equal(matchesSearch("ALA", "Alabama"), true);
  assert.equal(matchesSearch("zzz", "Alabama"), false);
});

test("ticks and domains are deterministic", () => {
  assert.deepEqual(niceTicks(0, 1, 5), [0, 0.2, 0.4, 0.6, 0.8, 1]);
  assert.deepEqual(niceTicks(-0.25, 0.25, 5), [-0.2, -0.1, 0, 0.1, 0.2]);
  assert.deepEqual(niceTicks(3, 3), [3]);
  assert.deepEqual(niceTicks(Number.NaN, 1), []);
  assert.deepEqual(domainFor([]), [0, 1]);
  assert.deepEqual(domainFor([2, 2]), [1.5, 2.5]);
  const [lo, hi] = domainFor([0, 10], 0.1);
  assert.ok(lo === -1 && hi === 11);
});

test("team metadata falls back when a school has no published colors", () => {
  assert.equal(teamAbbr("Nowhere State"), "NS");
  assert.equal(teamAbbr("Tulane").length > 0, true);
  assert.equal(teamColor("Nowhere State"), FALLBACK_TEAM_COLOR);
  assert.equal(teamAltColor("Nowhere State"), null);
  assert.match(teamColor("Michigan"), /^#[0-9a-f]{6}$/);
  assert.equal(teamAbbr("Appalachian State"), teamAbbr("App State"));
});

/** Yardage of one mirrored team-game: [yards_n, explosive_n, success_yards_n, success_yards_sum] per offense. */
function yardage(gameId: number, team: string, own: number[], other: number[]): TeamGameYardageRow {
  return {
    gameId, team,
    offYardsN: own[0], offExplosiveN: own[1], offSuccessYardsN: own[2], offSuccessYardsSum: own[3],
    defYardsN: other[0], defExplosiveN: other[1], defSuccessYardsN: other[2], defSuccessYardsSum: other[3],
  };
}

function yardageGames(): TeamGameRow[] {
  const rows = [
    ...game(1, 0, ["Alabama", 30, 10, 6], ["Michigan", 10, 10, 4]),
    ...game(2, 1, ["Alabama", 30, 20, 8], ["Tulane", 10, 10, 2]),
    ...game(3, 5, ["Michigan", 30, 10, 10], ["Tulane", 10, 10, 10]), // after the window
  ];
  const offense: Record<string, number[]> = {
    "1:Alabama": [10, 2, 6, 60], "1:Michigan": [9, 0, 4, 30],
    "2:Alabama": [30, 1, 8, 100], "2:Tulane": [10, 1, 0, 0],
    "3:Michigan": [10, 9, 10, 500], "3:Tulane": [10, 9, 10, 500],
  };
  const counts = rows.map((r) => yardage(r.gameId, r.team, offense[`${r.gameId}:${r.team}`], offense[`${r.gameId}:${r.opponent}`]));
  return withYardage(rows, [...counts].reverse());
}

test("efficiency: 20+ rate and yards/success come from release window sums with pooled averages", () => {
  const rows = yardageGames();
  const explosive = efficiencyPoints(roster, rows, 1, "offense", "explosive_rate");
  const alabama = explosive.points.find((p) => p.team === "Alabama")!;
  assert.deepEqual([alabama.x, alabama.y, alabama.n], [14 / 30, 3 / 40, 40], "ratio of sums, not mean of game rates");
  assert.equal(explosive.points.find((p) => p.team === "Michigan")!.y, 0, "zero explosive plays over real exposure is zero");
  assert.deepEqual(explosive.average, { x: (14 + 4 + 2) / 50, y: (2 + 0 + 1 + 1) / (10 + 9 + 30 + 10) });
  assert.deepEqual(explosive.unavailable, ["Idle State", "Notre Dame"]);

  const perSuccess = efficiencyPoints(roster, rows, 1, "offense", "yards_per_success");
  assert.deepEqual(perSuccess.points.map((p) => p.team), ["Alabama", "Michigan"]);
  assert.deepEqual(perSuccess.points.map((p) => [p.y, p.n]), [[160 / 14, 40], [30 / 4, 9]]);
  assert.ok(perSuccess.unavailable.includes("Tulane"), "zero successful yardage plays is unavailable, never zero");
  assert.deepEqual(perSuccess.average, { x: 20 / 50, y: (60 + 30 + 100 + 0) / (6 + 4 + 8 + 0) });
  assert.deepEqual([perSuccess.invertX, perSuccess.invertY], [false, false]);
});

test("efficiency: defense yardage is the opponent's offense, with inverted axes", () => {
  const defense = efficiencyPoints(roster, yardageGames(), 1, "defense", "explosive_rate");
  const tulane = defense.points.find((p) => p.team === "Tulane")!;
  assert.deepEqual([tulane.y, tulane.n], [1 / 30, 30]);
  assert.deepEqual([defense.invertX, defense.invertY], [true, true]);
  assert.equal(efficiencyPoints(roster, yardageGames(), 1, "defense", "yards_per_success").points.find((p) => p.team === "Michigan")!.y, 10);
});

test("efficiency: rows without yardage (a charts_v1 release) plot nothing for explosiveness", () => {
  const rows = game(1, 0, ["Alabama", 30, 10, 6], ["Michigan", 10, 10, 4]);
  for (const metric of ["explosive_rate", "yards_per_success"] as const) {
    const data = efficiencyPoints(roster, rows, 1, "offense", metric);
    assert.deepEqual([data.points, data.average], [[], null]);
    assert.equal(data.unavailable.length, roster.length);
  }
  assert.equal(efficiencyPoints(roster, rows, 1, "offense", "ppa").points.length, 2);
});

test("yardage joins by game and team and rejects differing key sets", () => {
  const rows = game(1, 0, ["Alabama", 30, 10, 6], ["Michigan", 10, 10, 4]);
  const counts = [yardage(1, "Michigan", [9, 1, 4, 30], [10, 2, 6, 60]), yardage(1, "Alabama", [10, 2, 6, 60], [9, 1, 4, 30])];
  const joined = withYardage(rows, counts);
  assert.deepEqual(joined.map((r) => [r.team, r.offYardsN, r.defExplosiveN, r.offSuccessSum]), [["Alabama", 10, 1, 6], ["Michigan", 9, 2, 4]]);
  assert.throws(() => withYardage(rows, counts.slice(1)), /keys differ/);
  assert.throws(() => withYardage(rows, [...counts, yardage(2, "Tulane", [1, 0, 0, 0], [1, 0, 0, 0])]), /keys differ/);
  assert.throws(() => withYardage(rows, [counts[0], { ...counts[1], gameId: 2 }]), /keys differ/);
  assert.throws(() => withYardage(rows, [counts[0], counts[0]]), /keys differ/);
});

test("bar colors keep a visible mid-tone on both themes", () => {
  assert.equal(chartColor("#2563eb", null, "#64748b"), "#2563eb");
  assert.equal(chartColor("#00274c", "#ffcb05", "#64748b"), "#ffcb05", "navy vanishes on the dark theme");
  assert.equal(chartColor("#ffffff", "#ffcb05", "#64748b"), "#ffcb05", "near-white primary falls back to the alternate");
  assert.equal(chartColor("#000000", "#111111", "#64748b"), "#64748b", "no visible color → neutral fallback");
  assert.equal(chartColor("bad", null, "#64748b"), "#64748b");
  assert.ok(relativeLuminance("#ffffff") > 0.99 && relativeLuminance("#000000") === 0);
  assert.equal(formatPercent(0.4821), "48.2%");
  assert.equal(formatEpa(0.1214), "+0.121");
  assert.equal(formatEpa(-0.05), "-0.050");
});


test("actual game filtering includes either team and preserves bar ordering", () => {
  const { bars } = netSuccessBars([
    ...game(1, 2, ["Alabama", 10, 10, 3], ["Tulane", 20, 10, 5]),
    ...game(2, 2, ["Michigan", 20, 10, 7], ["Notre Dame", 10, 10, 3]),
  ], 2);
  assert.deepEqual(filterNetSuccessBars(bars, roster, "SEC").map((b) => b.gameId), [1], "losing selected-group team includes game");
  assert.deepEqual(filterNetSuccessBars(bars, roster, "p4"), bars);
  assert.deepEqual(filterNetSuccessBars(bars, roster, "Sun Belt"), []);
});

test("national ranks use competition ties and independent axis directions before filtering", () => {
  const points = [
    { team: "A", conference: "SEC", x: 0.6, y: 0.1, n: 10 },
    { team: "B", conference: "SEC", x: 0.6, y: 0.3, n: 30 },
    { team: "C", conference: "Big Ten", x: 0.4, y: 0.1, n: 10 },
  ];
  const base = { points, average: { x: 0.56, y: 0.22 }, unavailable: [], invertX: false, invertY: false };
  const ranks = scatterRanks(base);
  assert.deepEqual([...ranks.values()], [{ x: 1, y: 2 }, { x: 1, y: 1 }, { x: 3, y: 2 }]);
  const defense = scatterRanks({ ...base, invertX: true, invertY: true });
  assert.deepEqual([...defense.values()], [{ x: 2, y: 1 }, { x: 2, y: 3 }, { x: 1, y: 1 }]);
  const adjusted = scatterRanks({ ...base, invertY: true });
  assert.deepEqual(adjusted.get("A"), { x: 1, y: 1 });
  const filtered = points.filter((p) => p.conference === "Big Ten");
  assert.equal(ranks.get(filtered[0].team)?.x, 3, "national rank stays national in small groups");
});

test("cumulative profile pools unequal independent exposures and excludes later games", () => {
  const rows = [
    row({ gameId: 1, week: 1, team: "Alabama", opponent: "Michigan", offSuccessN: 10, offSuccessSum: 8, offEpaN: 5, offEpaSum: 1 }),
    row({ gameId: 2, week: 2, team: "Alabama", opponent: "Tulane", offSuccessN: 90, offSuccessSum: 36, offEpaN: 30, offEpaSum: 0 }),
    row({ gameId: 3, week: 3, team: "Alabama", opponent: "Tulane", offSuccessN: 10, offSuccessSum: 10, offEpaN: 10, offEpaSum: 10 }),
  ];
  const profile = efficiencyPoints(roster, rows, 2, "offense");
  assert.equal(profile.points[0].x, 44 / 100);
  assert.equal(profile.points[0].y, 1 / 35);
  assert.deepEqual(profile.average, { x: 44 / 100, y: 1 / 35 });
});

test("buildConferenceMap and matchesTeamConference resolve CFBD and legacy rating/game names", () => {
  const map = buildConferenceMap([
    { team: "App State", conference: "Sun Belt" },
    { team: "Southern Mississippi", conference: "Sun Belt" },
    { team: "Notre Dame", conference: "FBS Independents" },
    { team: "Texas", conference: "SEC" },
  ]);
  assert.equal(map.get("App State"), "Sun Belt");
  assert.equal(map.get("Appalachian State"), "Sun Belt");
  assert.equal(map.get("Southern Miss"), "Sun Belt");
  assert.equal(map.get("Southern Mississippi"), "Sun Belt");
  assert.equal(matchesTeamConference("Sun Belt", "Appalachian State", map), true);
  assert.equal(matchesTeamConference("Sun Belt", "Southern Miss", map), true);
  assert.equal(matchesTeamConference("p4", "Notre Dame", map), true);
  assert.equal(matchesTeamConference("p4", "Texas", map), true);
  assert.equal(matchesTeamConference("p4", "App State", map), false);
});
