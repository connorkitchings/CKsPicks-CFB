import type { Game, HistoricalModelContext, Stats } from "@/lib/queries";
import type { PublicationMode } from "@/lib/publication";
import type { Performance, Rating } from "@/lib/v5";

const startDate = new Date("2026-08-29T19:30:00.000Z");

export const v5RatingFixture: Rating = {
  team: "Texas", week: 0, cutoffUtc: startDate,
  offenseRating: 3.4, offenseVariance: 1.44,
  defenseRating: 2.1, defenseVariance: 1.21,
  overallRating: 5.5, overallVariance: 2.65,
  fallbackReason: null,
};

export const v5PerformanceFixture: Performance[] = [
  { classification: "all", games: 2, evaluated: 2, marginMae: 4.5,
    totalMae: 6, marginCoverage95: 1, totalCoverage95: 0.5,
    spread: { win: 1, loss: 0, push: 0 }, total: { win: 0, loss: 1, push: 0 } },
  { classification: "replay", games: 1, evaluated: 1, marginMae: 5,
    totalMae: 7, marginCoverage95: 1, totalCoverage95: 0,
    spread: { win: 0, loss: 0, push: 0 }, total: { win: 0, loss: 0, push: 0 } },
  { classification: "live", games: 1, evaluated: 1, marginMae: 4,
    totalMae: 5, marginCoverage95: 1, totalCoverage95: 1,
    spread: { win: 1, loss: 0, push: 0 }, total: { win: 0, loss: 1, push: 0 } },
];

export const v5PerformanceBeforeWeekZeroFixture: Performance[] = [
  { classification: "all", games: 0, evaluated: 0, marginMae: null,
    totalMae: null, marginCoverage95: null, totalCoverage95: null,
    spread: { win: 0, loss: 0, push: 0 }, total: { win: 0, loss: 0, push: 0 } },
  { classification: "replay", games: 0, evaluated: 0, marginMae: null,
    totalMae: null, marginCoverage95: null, totalCoverage95: null,
    spread: { win: 0, loss: 0, push: 0 }, total: { win: 0, loss: 0, push: 0 } },
  { classification: "live", games: 0, evaluated: 0, marginMae: null,
    totalMae: null, marginCoverage95: null, totalCoverage95: null,
    spread: { win: 0, loss: 0, push: 0 }, total: { win: 0, loss: 0, push: 0 } },
];

const base = {
  gameId: 401000001,
  season: 2026,
  week: 0,
  startDate,
  homeTeam: "Texas",
  awayTeam: "Ohio State",
  homeTeamSpreadLine: -2.5,
  totalLine: 51.5,
  updatedAt: startDate,
  homePoints: 24,
  awayPoints: 21,
  homeRecord: null,
  awayRecord: "1-0",
};

const v5PredictionRun = {
  runId: "fixture-v5-run",
  systemName: "Trench Warfare V5",
  modelId: "v5-possession-ppp-rho060-exposure",
  evidenceClass: "replay" as const,
  spreadModelVersion: "fixture-v5",
  totalModelVersion: "fixture-v5",
};

const v4FallbackRun = {
  runId: "fixture-v4-run",
  systemName: "Trench Warfare V4",
  modelId: "week0-2026-v4-strict-20260818-r2",
  evidenceClass: "legacy" as const,
  spreadModelVersion: "fixture-v4",
  totalModelVersion: "fixture-v4",
};

export function uiFixture(
  mode: PublicationMode,
  week = 0,
): { games: Game[]; stats: Stats | null; historicalContext: HistoricalModelContext | null; weeks: number[]; performance: Performance[] } {
  const shared = { ...base, week };
  if (mode === "market") {
    return {
      games: [
        {
          ...shared,
          publicationMode: "market",
          spreadResult: "win",
          totalResult: "push",
        },
      ],
      stats: null,
      historicalContext: null,
      weeks: [0, 1, 2],
      performance: [],
    };
  }
  // Week 0 selects V5 (replay evidence); week 1 exercises a legacy V4
  // fallback selection, which renders its own model without the V5 banner.
  const run = week === 1 ? v4FallbackRun : v5PredictionRun;
  return {
    games: [
      {
        ...shared,
        publicationMode: "predictions",
        runId: run.runId,
        runState: "scored",
        predictedSpread: 3.5,
        predictedTotal: 52.0,
        predictedSpreadStdDev: null,
        predictedTotalStdDev: null,
        spreadLean: "home",
        totalLean: "over",
        edgeSpread: 1,
        edgeTotal: 0.5,
        highConfidence: false,
        systemName: run.systemName,
        modelId: run.modelId,
        regime: "game_1",
        homeCompletedGames: 0,
        awayCompletedGames: 0,
        spreadModelVersion: run.spreadModelVersion,
        totalModelVersion: run.totalModelVersion,
        spreadResult: "loss",
        totalResult: "win",
        evidenceClass: run.evidenceClass,
      },
    ],
    stats: {
      season: 2026,
      // Week 1 is pregame in the fixture, so its moment-of-record stays Week 0.
      asOfWeek: 0,
      spreadWins: 1,
      spreadLosses: 1,
      spreadPushes: 0,
      totalWins: 1,
      totalLosses: 0,
      totalPushes: 1,
    },
    historicalContext: {
      modelId: "week0-2026-v4-strict-20260818-r2",
      fullSeason: { comparisonSeason: 2025, comparisonWeek: null, spreadWins: 379, spreadLosses: 366, spreadPushes: 16, spreadComparedGames: 761, totalWins: 398, totalLosses: 358, totalPushes: 5, totalComparedGames: 761 },
      matchingWeek: week === 0 ? null : { comparisonSeason: 2025, comparisonWeek: week, spreadWins: 26, spreadLosses: 22, spreadPushes: 2, spreadComparedGames: 50, totalWins: 28, totalLosses: 22, totalPushes: 0, totalComparedGames: 50 },
    },
    weeks: [0, 1, 2],
    performance: run === v5PredictionRun
      ? week === 0 ? v5PerformanceBeforeWeekZeroFixture : v5PerformanceFixture
      : [],
  };
}
