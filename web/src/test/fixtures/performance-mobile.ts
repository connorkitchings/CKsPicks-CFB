import type { BetRecord, GradedGamePick, PerformanceDetail, PerformanceSummary } from "@/lib/v5";
import { v5PerformanceDetailFixture } from "./publication";

const PRE = "model_side_best_quote_v2:retained_prekickoff";
const RETRO = "model_side_best_quote_v2:cfbd_retrospective";

const originalGame = v5PerformanceDetailFixture.gradedGames[0];

/*
 * Hand-derived expectations (actual home margin / total; model and line errors are prediction minus
 * actual; the line-implied home margin is minus the canonical spread):
 *
 * Spread, pre-kickoff comparison set (7 games; game 8 is retrospective, game 3 has no forecast):
 *   game  model err  line err
 *   1     +0.5       -0.5      exact tie ("even")
 *   2     +12        +10.5
 *   4     +3         0         pushed at the line
 *   5     -21        -21.5
 *   6     +1.5       +3        pick'em, canonical spread 0
 *   7     +3         0         pushed at the line
 *   9     -35        -25       model big miss (> 28)
 *   average miss 76/7 = 10.9 model, 60.5/7 = 8.6 line; lean -36/7 = -5.1 and -33.5/7 = -4.8;
 *   model closer in 2, line closer in 4, even 1 (decided 6)
 * Totals, pre-kickoff comparison set (7 games; game 8 retrospective, game 4 ungraded):
 *   game  model err  line err
 *   1     +7         +6.5
 *   2     +3         0
 *   3     +3         -3.5
 *   5     +7         0
 *   6     +7         +8.5
 *   7     -6         -4
 *   9     +3         -4
 *   average miss 36/7 = 5.1 model, 26.5/7 = 3.8 line; lean +3.4 and +0.5;
 *   model closer in 3, line closer in 4
 * Records: spread 3-3-2 and totals 3-3-2 (50.0%, -2.4 pp vs 52.4%).
 */
const games: GradedGamePick[] = [
  {
    ...originalGame,
    canonicalSpread: -2.5,
    canonicalTotal: 51.5,
    spreadGradingVersion: PRE,
    totalGradingVersion: PRE,
  },
  {
    ...originalGame,
    gameId: 401000002,
    week: 1,
    startDate: new Date("2026-09-05T19:30:00.000Z"),
    awayTeam: "Georgia",
    homeTeam: "Alabama",
    awayPoints: 27,
    homePoints: 20,
    marketSpread: -3.5,
    predictedSpread: 5,
    spreadLean: "home",
    spreadResult: "loss",
    spreadEdge: 1.5,
    marketTotal: 47,
    predictedTotal: 50,
    totalLean: "over",
    totalResult: "push",
    totalEdge: 3,
    spreadPriceProvenance: "actual",
    totalPriceProvenance: "defaulted",
    canonicalSpread: -3.5,
    canonicalTotal: 47,
    spreadGradingVersion: PRE,
    totalGradingVersion: PRE,
  },
  {
    ...originalGame,
    gameId: 401000003,
    week: 1,
    startDate: new Date("2026-09-05T23:30:00.000Z"),
    awayTeam: "Southern Mississippi",
    homeTeam: "Appalachian State",
    awayPoints: 21,
    homePoints: 28,
    marketSpread: null,
    predictedSpread: null,
    spreadLean: null,
    spreadResult: null,
    spreadEdge: null,
    marketTotal: 45.5,
    predictedTotal: 52,
    totalLean: "over",
    totalResult: "win",
    totalEdge: 6.5,
    totalPriceProvenance: "actual",
    canonicalSpread: null,
    canonicalTotal: 45.5,
    spreadGradingVersion: null,
    totalGradingVersion: PRE,
  },
  {
    ...originalGame,
    gameId: 401000004,
    runId: "fixture-v5-long-run-identifier-for-mobile-provenance-wrapping-2026-week-two",
    freezeReceiptSha256: "a".repeat(64),
    week: 2,
    startDate: new Date("2026-09-12T19:30:00.000Z"),
    awayTeam: "Notre Dame",
    homeTeam: "Clemson",
    awayPoints: 21,
    homePoints: 24,
    marketSpread: -3,
    predictedSpread: 6,
    spreadLean: "home",
    spreadResult: "push",
    spreadEdge: 3,
    marketTotal: null,
    predictedTotal: 49,
    totalLean: null,
    totalResult: null,
    totalEdge: null,
    spreadPriceProvenance: "unavailable",
    canonicalSpread: -3,
    canonicalTotal: null,
    spreadGradingVersion: PRE,
    totalGradingVersion: null,
  },
  {
    ...originalGame,
    gameId: 401000005,
    week: 2,
    startDate: new Date("2026-09-12T23:30:00.000Z"),
    awayTeam: "Washington",
    homeTeam: "Oregon",
    awayPoints: 10,
    homePoints: 38,
    marketSpread: -6.5,
    predictedSpread: 7,
    spreadLean: "home",
    spreadResult: "win",
    spreadEdge: 0.5,
    marketTotal: 48,
    predictedTotal: 55,
    totalLean: "over",
    totalResult: "push",
    totalEdge: 7,
    canonicalSpread: -6.5,
    canonicalTotal: 48,
    spreadGradingVersion: PRE,
    totalGradingVersion: PRE,
  },
  {
    ...originalGame,
    gameId: 401000006,
    week: 2,
    startDate: new Date("2026-09-13T00:00:00.000Z"),
    awayTeam: "Penn State",
    homeTeam: "Michigan",
    awayPoints: 20,
    homePoints: 17,
    marketSpread: 0,
    predictedSpread: -1.5,
    spreadLean: "away",
    spreadResult: "win",
    spreadEdge: 1.5,
    marketTotal: 45.5,
    predictedTotal: 44,
    totalLean: "under",
    totalResult: "win",
    totalEdge: 1.5,
    canonicalSpread: 0,
    canonicalTotal: 45.5,
    spreadGradingVersion: PRE,
    totalGradingVersion: PRE,
  },
  {
    ...originalGame,
    gameId: 401000007,
    week: 3,
    startDate: new Date("2026-09-19T19:30:00.000Z"),
    awayTeam: "LSU",
    homeTeam: "Florida",
    awayPoints: 25,
    homePoints: 31,
    marketSpread: -6,
    predictedSpread: 9,
    spreadLean: "home",
    spreadResult: "push",
    spreadEdge: 3,
    marketTotal: 52,
    predictedTotal: 50,
    totalLean: "under",
    totalResult: "loss",
    totalEdge: 2,
    canonicalSpread: -6,
    canonicalTotal: 52,
    spreadGradingVersion: PRE,
    totalGradingVersion: PRE,
  },
  {
    // Graded against a retrospective line: counted in the footnote, not compared.
    ...originalGame,
    gameId: 401000008,
    week: 3,
    startDate: new Date("2026-09-19T23:30:00.000Z"),
    awayTeam: "Iowa State",
    homeTeam: "Kansas",
    awayPoints: 24,
    homePoints: 14,
    marketSpread: -2,
    predictedSpread: 3,
    spreadLean: "home",
    spreadResult: "loss",
    spreadEdge: 1,
    marketTotal: 49,
    predictedTotal: 50,
    totalLean: "over",
    totalResult: "loss",
    totalEdge: 1,
    canonicalSpread: -2,
    canonicalTotal: 49,
    spreadGradingVersion: RETRO,
    totalGradingVersion: RETRO,
  },
  {
    // The model's biggest miss: a blowout well past the 28 point threshold.
    ...originalGame,
    gameId: 401000009,
    week: 3,
    startDate: new Date("2026-09-20T00:00:00.000Z"),
    awayTeam: "Wyoming",
    homeTeam: "Boise State",
    awayPoints: 7,
    homePoints: 52,
    marketSpread: -20,
    predictedSpread: 10,
    spreadLean: "away",
    spreadResult: "loss",
    spreadEdge: 10,
    marketTotal: 55,
    predictedTotal: 62,
    totalLean: "over",
    totalResult: "win",
    totalEdge: 7,
    canonicalSpread: -20,
    canonicalTotal: 55,
    spreadGradingVersion: PRE,
    totalGradingVersion: PRE,
  },
];

function record(results: ("win" | "loss" | "push" | null)[]): BetRecord {
  const win = results.filter((result) => result === "win").length;
  const loss = results.filter((result) => result === "loss").length;
  const push = results.filter((result) => result === "push").length;
  return { win, loss, push, winRate: win + loss ? (100 * win) / (win + loss) : 0 };
}

function summary(rows: GradedGamePick[]): PerformanceSummary {
  return {
    classification: "all",
    games: rows.length,
    evaluated: rows.filter((game) => game.predictedSpread !== null).length,
    spread: record(rows.map((game) => game.spreadResult)),
    total: record(rows.map((game) => game.totalResult)),
    combined: record(rows.flatMap((game) => [game.spreadResult, game.totalResult])),
    // Synthetic season diagnostics are unchanged; the mobile fixture exercises record navigation.
    marginMae: 4.5,
    totalMae: 6,
    marginCoverage95: 100,
    totalCoverage95: 50,
  };
}

function detail(rows: GradedGamePick[], weeks: number[], ungradedByWeek: Record<number, number>, selectedExtra: number): PerformanceDetail {
  return {
    classification: "all",
    selectedGames: rows.length + selectedExtra,
    summary: summary(rows),
    byWeek: Object.fromEntries(weeks.map((week) => [week, summary(rows.filter((game) => game.week === week))])),
    weeks,
    weekRows: weeks.map((week) => ({ week, ungradedGames: ungradedByWeek[week] ?? 0, unplayedGames: ungradedByWeek[week] ?? 0 })),
    gradedGames: rows,
  };
}

/** Separate UI fixture leaves existing numerical/publication fixtures unchanged. Week 3 is still in progress. */
export const mobilePerformanceFixture: PerformanceDetail = detail(games, [0, 1, 2, 3], { 3: 2 }, 2);

/** `/model?fixture=partial`: one graded week and no retained lines, for the empty states. */
export const partialPerformanceFixture: PerformanceDetail = detail(
  [{ ...games[0], canonicalSpread: null, canonicalTotal: null, spreadGradingVersion: null, totalGradingVersion: null }],
  [0],
  {},
  0,
);
