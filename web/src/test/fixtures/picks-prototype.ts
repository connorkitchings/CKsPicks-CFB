import type { Game, PredictionGame } from "@/lib/queries";
import type { Performance } from "@/lib/v5";

/**
 * Sample slate for the /test Picks prototype (only loaded when
 * CFB_UI_TEST_MODE=1). Covers: strong/weak leans, home and away spread leans,
 * over and under, a high-confidence star, a no-lean game, a missing total line,
 * and one finished game.
 */
const published = new Date("2026-09-29T23:24:00Z");

type Spec = {
  id: number;
  start: string;
  away: string;
  home: string;
  awayRecord: string | null;
  homeRecord: string | null;
  homeLine: number | null;
  total: number | null;
  predSpread: number | null; // home margin
  predTotal: number | null;
  hc?: boolean;
  final?: [number, number];
};

const specs: Spec[] = [
  { id: 1, start: "2026-10-01T22:00:00Z", away: "Western Kentucky", home: "Utah", awayRecord: "0-3", homeRecord: "0-3", homeLine: -2.5, total: 57.5, predSpread: 7.6, predTotal: 54.1 },
  { id: 2, start: "2026-10-01T23:30:00Z", away: "Wisconsin", home: "Washington", awayRecord: "2-1", homeRecord: "1-2", homeLine: 3, total: 46.5, predSpread: -2.6, predTotal: 46.9 },
  { id: 3, start: "2026-10-02T23:00:00Z", away: "Oregon", home: "USC", awayRecord: "3-0", homeRecord: "2-1", homeLine: 2.5, total: 61.5, predSpread: -9.1, predTotal: 70.2, hc: true },
  { id: 4, start: "2026-10-03T16:00:00Z", away: "Georgia", home: "Alabama", awayRecord: "3-0", homeRecord: "3-0", homeLine: 1.5, total: 52.5, predSpread: 0.4, predTotal: 51.8 },
  { id: 5, start: "2026-10-03T16:00:00Z", away: "Michigan", home: "Penn State", awayRecord: "2-1", homeRecord: "3-0", homeLine: -6.5, total: 44.5, predSpread: 10.2, predTotal: 41.0 },
  { id: 6, start: "2026-10-03T19:30:00Z", away: "Notre Dame", home: "Clemson", awayRecord: "2-1", homeRecord: "2-1", homeLine: -1, total: 49.5, predSpread: 3.4, predTotal: 56.9, hc: true },
  { id: 7, start: "2026-10-03T23:30:00Z", away: "LSU", home: "Tennessee", awayRecord: "3-0", homeRecord: "3-0", homeLine: -4.5, total: null, predSpread: 5.0, predTotal: 58.3 },
  { id: 8, start: "2026-10-03T23:30:00Z", away: "Miami", home: "Florida State", awayRecord: "3-0", homeRecord: "1-2", homeLine: 7.5, total: 55.5, predSpread: -3.0, predTotal: 54.9 },
  { id: 9, start: "2026-10-04T00:00:00Z", away: "Texas", home: "Oklahoma", awayRecord: "3-0", homeRecord: "2-1", homeLine: 4, total: 50.5, predSpread: 2.0, predTotal: 50.0 },
  { id: 10, start: "2026-09-26T16:00:00Z", away: "Ohio State", home: "Michigan", awayRecord: "3-0", homeRecord: "2-0", homeLine: 6, total: 47.5, predSpread: -8.6, predTotal: 49.4, final: [24, 17] },
];

/** Minimum model-vs-market gap (points) that produces a lean. */
const NO_BET = 1.0;

export function protoGames(): Game[] {
  return specs.map((s): PredictionGame => {
    // Derive leans and edges from the numbers so the sample is self-consistent.
    const spreadGap =
      s.predSpread !== null && s.homeLine !== null ? s.predSpread + s.homeLine : null;
    const spreadLean: PredictionGame["spreadLean"] =
      spreadGap !== null && Math.abs(spreadGap) >= NO_BET ? (spreadGap > 0 ? "home" : "away") : null;
    const totalGap =
      s.predTotal !== null && s.total !== null ? s.predTotal - s.total : null;
    const totalLean: PredictionGame["totalLean"] =
      totalGap !== null && Math.abs(totalGap) >= NO_BET ? (totalGap > 0 ? "over" : "under") : null;
    return {
    gameId: s.id,
    season: 2026,
    week: 5,
    startDate: new Date(s.start),
    homeTeam: s.home,
    awayTeam: s.away,
    homeTeamSpreadLine: s.homeLine,
    totalLine: s.total,
    updatedAt: published,
    homePoints: s.final ? s.final[1] : null,
    awayPoints: s.final ? s.final[0] : null,
    homeRecord: s.homeRecord,
    awayRecord: s.awayRecord,
    publicationMode: "predictions",
    runId: "proto-run",
    runState: "frozen",
    predictedSpread: s.predSpread,
    predictedTotal: s.predTotal,
    predictedSpreadStdDev: null,
    predictedTotalStdDev: null,
    spreadLean,
    totalLean,
    edgeSpread: spreadLean && spreadGap !== null ? Math.abs(spreadGap) : null,
    edgeTotal: totalLean && totalGap !== null ? Math.abs(totalGap) : null,
    highConfidence: Boolean(s.hc),
    systemName: "Trench Warfare V5",
    modelId: "v5-possession-ppp-rho060-exposure",
    evidenceClass: "live",
    regime: null,
    homeCompletedGames: 3,
    awayCompletedGames: 3,
    spreadModelVersion: null,
    totalModelVersion: null,
    spreadResult: null,
    totalResult: null,
    };
  });
}

export const protoPerformance: Performance[] = [
  { classification: "all", games: 215, evaluated: 215, marginMae: 14.5, totalMae: 13.4, marginCoverage95: 0.95, totalCoverage95: 0.95, spread: { win: 93, loss: 103, push: 3 }, total: { win: 82, loss: 77, push: 0 } },
  { classification: "replay", games: 215, evaluated: 215, marginMae: 14.5, totalMae: 13.4, marginCoverage95: 0.95, totalCoverage95: 0.95, spread: { win: 93, loss: 103, push: 3 }, total: { win: 82, loss: 77, push: 0 } },
  { classification: "live", games: 0, evaluated: 0, marginMae: null, totalMae: null, marginCoverage95: null, totalCoverage95: null, spread: { win: 0, loss: 0, push: 0 }, total: { win: 0, loss: 0, push: 0 } },
];

export const protoRanks: Record<string, number> = {
  Georgia: 2, Alabama: 5, Oregon: 3, USC: 18, Michigan: 11, "Penn State": 7, "Notre Dame": 9,
  Clemson: 14, LSU: 8, Tennessee: 12, Miami: 16, "Florida State": 31, Texas: 4, Oklahoma: 22,
  "Ohio State": 1, Wisconsin: 27, Washington: 35, Utah: 41, "Western Kentucky": 97,
};
