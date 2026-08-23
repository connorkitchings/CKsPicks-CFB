import type { Game, Stats } from "@/lib/queries";
import type { PublicationMode } from "@/lib/publication";

const startDate = new Date("2026-08-29T19:30:00.000Z");

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
};

export function uiFixture(
  mode: PublicationMode,
  week = 0,
): { games: Game[]; stats: Stats | null; weeks: number[] } {
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
      weeks: [0, 1],
    };
  }
  return {
    games: [
      {
        ...shared,
        publicationMode: "predictions",
        runId: "fixture-run",
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
        systemName: "Fixture Model",
        modelId: "fixture-v1",
        regime: "established",
        homeCompletedGames: 4,
        awayCompletedGames: 4,
        spreadModelVersion: "fixture-v1",
        totalModelVersion: "fixture-v1",
        spreadResult: "loss",
        totalResult: "win",
      },
    ],
    stats: {
      season: 2026,
      asOfWeek: week,
      spreadWins: 1,
      spreadLosses: 1,
      spreadPushes: 0,
      totalWins: 1,
      totalLosses: 0,
      totalPushes: 1,
      updatedAt: startDate,
    },
    weeks: [0, 1],
  };
}
