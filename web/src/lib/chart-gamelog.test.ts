import assert from "node:assert/strict";
import test from "node:test";
import { describeGameLogGame, gameLogMetrics, parseGameLogMetric, rankText } from "./chart-config.ts";
import {
  defaultGameLogTeam,
  efficiencyPoints,
  scatterRanks,
  teamGameLog,
  withYardage,
  type AdjustedRow,
  type RosterRow,
  type TeamGameRow,
} from "./charts.ts";

const roster: RosterRow[] = [
  { team: "Alpha", conference: "East" },
  { team: "Bravo", conference: "East" },
  { team: "Charlie", conference: "West" },
  { team: "Delta", conference: "West" },
];

/** One team-game side: `plays` plays, `success` successes and `epa` total EPA, mirrored onto the opponent's defense. */
type Side = { plays: number; success: number; epa: number };

function game(week: number, gameId: number, home: string, away: string, h: Side, a: Side, points: [number, number]): TeamGameRow[] {
  const row = (team: string, opponent: string, site: "home" | "away", own: Side, other: Side, pf: number, pa: number): TeamGameRow => ({
    week, gameId, team, opponent, site, pointsFor: pf, pointsAgainst: pa,
    offPlays: own.plays, offSuccessN: own.plays, offSuccessSum: own.success, offEpaN: own.plays, offEpaSum: own.epa,
    defPlays: other.plays, defSuccessN: other.plays, defSuccessSum: other.success, defEpaN: other.plays, defEpaSum: other.epa,
  });
  return [row(home, away, "home", h, a, points[0], points[1]), row(away, home, "away", a, h, points[1], points[0])];
}

// Listed out of order on purpose: week 2 before week 1, and game 21 before game 12.
const rows: TeamGameRow[] = [
  ...game(2, 21, "Alpha", "Charlie", { plays: 10, success: 6, epa: 2 }, { plays: 10, success: 3, epa: -1 }, [28, 14]),
  ...game(2, 20, "Bravo", "Delta", { plays: 20, success: 8, epa: 1 }, { plays: 10, success: 5, epa: 0.5 }, [17, 20]),
  ...game(1, 12, "Alpha", "Bravo", { plays: 10, success: 4, epa: 0 }, { plays: 10, success: 5, epa: 1 }, [10, 31]),
  ...game(1, 11, "Charlie", "Delta", { plays: 10, success: 5, epa: 1 }, { plays: 10, success: 5, epa: 1 }, [21, 21]),
];

test("game log: every team-game of the team, ordered by week then game id, with W/L/T results", () => {
  const sameWeek = [...rows, ...game(1, 5, "Alpha", "Delta", { plays: 10, success: 5, epa: 0 }, { plays: 10, success: 5, epa: 0 }, [3, 0])];
  const log = teamGameLog(roster, sameWeek, "Alpha", "success");
  assert.deepEqual(log.games.map((g) => [g.week, g.gameId, g.opponent, g.result]), [
    [1, 5, "Delta", "W 3-0"],
    [1, 12, "Bravo", "L 10-31"],
    [2, 21, "Charlie", "W 28-14"],
  ]);
  assert.equal(teamGameLog(roster, rows, "Charlie", "success").games[0].result, "T 21-21");
  assert.equal(log.games[1].offense, 0.4);
  assert.equal(log.games[1].defense, 0.5);
});

test("game log: the weekly FBS average is pooled over every team-game of that week", () => {
  const log = teamGameLog(roster, rows, "Alpha", "success");
  // Week 2 offense: (6 + 3 + 8 + 5) successes over (10 + 10 + 20 + 10) plays, not a mean of rates.
  const week2 = log.games.find((g) => g.week === 2)!;
  assert.equal(week2.average.offense, 22 / 50);
  // Every offense play is some team's defense play, so the pooled defense average is the same.
  assert.equal(week2.average.defense, 22 / 50);
  // Week 1: (4 + 5 + 5 + 5) / 40.
  assert.equal(log.games.find((g) => g.week === 1)!.average.offense, 19 / 40);
  const ppa = teamGameLog(roster, rows, "Alpha", "ppa").games.find((g) => g.week === 2)!;
  assert.equal(ppa.average.offense, (2 - 1 + 1 + 0.5) / 50);
});

test("game log: a zero denominator omits the value as n/a but keeps the game and leaves averages pooled", () => {
  const empty = game(3, 30, "Alpha", "Delta", { plays: 0, success: 0, epa: 0 }, { plays: 10, success: 4, epa: 1 }, [7, 3]);
  const log = teamGameLog(roster, [...rows, ...empty], "Alpha", "success");
  const week3 = log.games.find((g) => g.gameId === 30)!;
  assert.equal(log.games.length, 3);
  assert.equal(week3.offense, null);
  assert.equal(week3.defense, 0.4);
  assert.equal(week3.average.offense, 4 / 10);
  assert.match(describeGameLogGame("Alpha", week3, "success"), /offense n\/a/);

  // Without yardage (a `charts_v1` release) the explosive rate has no exposure anywhere.
  const noYardage = teamGameLog(roster, rows, "Alpha", "explosive_rate");
  assert.ok(noYardage.games.every((g) => g.offense === null && g.defense === null && g.average.offense === null));
});

test("game log: the explosive rate reads joined yardage", () => {
  const yardage = rows.map((r) => ({
    gameId: r.gameId, team: r.team,
    offYardsN: r.offPlays, offExplosiveN: r.team === "Alpha" ? 2 : 1, offSuccessYardsN: 0, offSuccessYardsSum: 0,
    defYardsN: r.defPlays, defExplosiveN: r.opponent === "Alpha" ? 2 : 1, defSuccessYardsN: 0, defSuccessYardsSum: 0,
  }));
  const log = teamGameLog(roster, withYardage(rows, yardage), "Alpha", "explosive_rate");
  assert.deepEqual(log.games.map((g) => g.offense), [0.2, 0.2]);
  assert.deepEqual(log.games.map((g) => g.defense), [0.1, 0.1]);
  // Week 1: (2 + 1 + 1 + 1) explosive plays over 40.
  assert.equal(log.games[0].average.offense, 5 / 40);
  // Week 2 has unequal exposures (10/10/20/10), so the average must be pooled.
  assert.equal(log.games[1].average.offense, 5 / 50);
  assert.equal(log.games[1].average.defense, 5 / 50);
  // The season FBS average pools both weeks: 10 explosive plays over 90.
  assert.deepEqual(log.season.offense, { value: 4 / 20, rank: 1, ranked: 4, average: 10 / 90 });
  assert.deepEqual(log.season.defense, { value: 2 / 20, rank: 2, ranked: 4, average: 10 / 90 });
});

test("game log header: season to date through the latest week with Efficiency's values and competition ranks", () => {
  for (const metric of ["success", "ppa"] as const) {
    for (const side of ["offense", "defense"] as const) {
      const efficiency = efficiencyPoints(roster, rows, 2, side, "ppa");
      const ranks = scatterRanks(efficiency);
      const axis = metric === "success" ? "x" : "y";
      for (const { team } of roster) {
        const log = teamGameLog(roster, rows, team, metric);
        assert.equal(log.throughWeek, 2);
        assert.deepEqual(log.season[side], {
          value: efficiency.points.find((p) => p.team === team)![axis],
          rank: ranks.get(team)![axis],
          ranked: 4,
          // The same pooled FBS average the Efficiency chart draws as its dashed line.
          average: efficiency.average![axis],
        }, `${team} ${metric} ${side}`);
      }
    }
  }
  // Offense success: Alpha 10/20, Bravo 13/30, Charlie 8/20, Delta 10/20 -> Alpha and Delta tie for 1st, Bravo 3rd.
  assert.deepEqual(["Alpha", "Delta", "Bravo", "Charlie"].map((team) => teamGameLog(roster, rows, team, "success").season.offense.rank), [1, 1, 3, 4]);
  // Defense allowed (lower is better): Alpha 8/20, Delta 13/30, Bravo 9/20, Charlie 11/20.
  assert.deepEqual(["Alpha", "Delta", "Bravo", "Charlie"].map((team) => teamGameLog(roster, rows, team, "success").season.defense.rank), [1, 2, 3, 4]);
  assert.equal(rankText(1, 4), "1st of 4");
  assert.equal(rankText(12, 133), "12th of 133");
  assert.equal(rankText(22, 133), "22nd of 133");
  assert.equal(rankText(null, 4), "");
});

test("game log header: a team without games is unranked and an empty release has no window", () => {
  const log = teamGameLog([...roster, { team: "Echo", conference: "West" }], rows, "Echo", "success");
  assert.deepEqual(log.games, []);
  // Even a team with no games gets the FBS average, 41 successful plays over 90.
  assert.deepEqual(log.season.offense, { value: null, rank: null, ranked: 4, average: 41 / 90 });
  assert.equal(teamGameLog(roster, [], "Alpha", "ppa").throughWeek, null);
});

function adjusted(asOfWeek: number, team: string, offense: number, defense: number): AdjustedRow[] {
  return (["offense", "defense"] as const).map((role) => ({
    asOfWeek, team, role, rawEpaPerPlay: 0, venueCorrection: 0, opponentAdjustment: 0,
    adjustedEpaPerPlay: role === "offense" ? offense : defense, epaN: 10, games: 1, adjustedRank: 1, cohortSize: 4,
  }));
}

test("default team: top adjusted net in the latest window, ties by name, within the conference group", () => {
  const windows = [
    ...adjusted(3, "Alpha", 0.5, -0.5), // best in an older window only
    ...adjusted(4, "Alpha", 0.1, 0.0),
    ...adjusted(4, "Charlie", 0.3, 0.1), // net 0.2
    ...adjusted(4, "Bravo", 0.3, 0.1), // ties Charlie: Bravo wins by name
    ...adjusted(4, "Delta", 0.0, 0.0),
  ];
  assert.equal(defaultGameLogTeam(roster, rows, windows), "Bravo");
  assert.equal(defaultGameLogTeam(roster, rows, windows, "West"), "Charlie");
  // A team missing a role cannot be charted on net.
  assert.equal(defaultGameLogTeam(roster, rows, windows.filter((r) => !(r.team === "Bravo" && r.role === "defense"))), "Charlie");
  // Without adjusted rows: the first team by name with a game in the group.
  assert.equal(defaultGameLogTeam(roster, rows, []), "Alpha");
  assert.equal(defaultGameLogTeam(roster, rows, [], "West"), "Charlie");
  assert.equal(defaultGameLogTeam(roster, [], []), null);
});

test("game log metrics: the explosive rate is offered only when yardage is served", () => {
  assert.deepEqual(gameLogMetrics(false), ["success", "ppa"]);
  assert.deepEqual(gameLogMetrics(true), ["success", "ppa", "explosive_rate"]);
  assert.equal(parseGameLogMetric("explosive_rate", true), "explosive_rate");
  assert.equal(parseGameLogMetric("explosive_rate", false), "success");
  assert.equal(parseGameLogMetric("ppa", false), "ppa");
  for (const raw of [undefined, null, "", "PPA", ["ppa"], "yards_per_success"]) assert.equal(parseGameLogMetric(raw, true), "success");
});
