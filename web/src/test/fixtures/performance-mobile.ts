import type { BetRecord, GradedGamePick, PerformanceDetail, PerformanceSummary } from "@/lib/v5";
import { v5PerformanceDetailFixture } from "./publication";

const originalGame = v5PerformanceDetailFixture.gradedGames[0];
const games: GradedGamePick[] = [
  originalGame,
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

/** Separate UI fixture leaves existing numerical/publication fixtures unchanged. */
export const mobilePerformanceFixture: PerformanceDetail = {
  classification: "all",
  selectedGames: games.length,
  summary: summary(games),
  byWeek: Object.fromEntries([0, 1, 2].map((week) => [week, summary(games.filter((game) => game.week === week))])),
  weeks: [0, 1, 2],
  gradedGames: games,
};
