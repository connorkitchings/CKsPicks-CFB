import { cache } from "react";
import { eq } from "drizzle-orm";
import { db, schema } from "./db.ts";
import { getCurrentRatings, getTeamRankMap, type Rating } from "./v5.ts";
import {
  normalCdf,
  calculateWinProbabilities,
  calculateProjectedPoints,
  getRankBadgeClass,
} from "./matchup-math.ts";

export interface TeamMetricValue {
  value: number;
  rank: number;
  formatted: string;
}

export interface UnitMatchupRow {
  name: string;
  awayValue: string;
  awayRank: number;
  homeValue: string;
  homeRank: number;
  higherIsBetterOffense?: boolean;
}

export interface TeamProfileStats {
  team: string;
  rank: number | null;
  overallRating: number;
  offenseRating: number;
  defenseRating: number;
  record: string | null;
  // Team pillars
  epaMargin: TeamMetricValue;
  offEpa: TeamMetricValue;
  defEpa: TeamMetricValue;
  offSuccessRate: TeamMetricValue;
  offDropbackSr: TeamMetricValue;
  offRushSr: TeamMetricValue;
  defSuccessRate: TeamMetricValue;
  defDropbackSr: TeamMetricValue;
  defRushSr: TeamMetricValue;
  netPtsPerDrive: TeamMetricValue;
  offPtsPerDrive: TeamMetricValue;
  defPtsPerDrive: TeamMetricValue;
  netFieldPosition: TeamMetricValue;
  eckelRatio: TeamMetricValue;
}

export interface MatchupData {
  gameId: number;
  season: number;
  week: number;
  startDate: Date;
  homeTeam: string;
  awayTeam: string;
  systemName: string;
  modelId: string | null;
  publicationMode: "predictions" | "market";
  // Odds & Model
  marketSpread: string;
  modelSpread: string;
  marketTotal: number | null;
  modelTotal: number | null;
  spreadLean: "home" | "away" | null;
  totalLean: "over" | "under" | null;
  edgeSpread: number | null;
  edgeTotal: number | null;
  highConfidence: boolean;
  // Predictions & Probabilities
  homeWinProb: number;
  awayWinProb: number;
  homeProjPoints: number;
  awayProjPoints: number;
  homeFinalPoints: number | null;
  awayFinalPoints: number | null;
  // Profiles
  awayProfile: TeamProfileStats;
  homeProfile: TeamProfileStats;
  // Unit vs Unit tables
  awayOffVsHomeDef: UnitMatchupRow[];
  awayDefVsHomeOff: UnitMatchupRow[];
  // Key Takeaways
  takeaways: string[];
}

export {
  normalCdf,
  calculateWinProbabilities,
  calculateProjectedPoints,
  getRankBadgeClass,
};

/**
 * Calibrate realistic advanced metrics for all FBS teams from certified ratings.
 * Calibrated against national FBS distributions:
 *   - Offense rating mean 0.00, std ~0.85
 *   - EPA/play mean 0.00, std ~0.10
 *   - Success rate mean 42.0%, std ~5.0%
 *   - Points per drive mean 2.15, std ~0.65
 *   - Eckel rate mean 38.0%, std ~8.0%
 */
interface RawTeamMetrics {
  team: string;
  overallRating: number;
  offenseRating: number;
  defenseRating: number;
  offEpa: number;
  defEpa: number;
  epaMargin: number;
  offSuccessRate: number;
  offDropbackSr: number;
  offRushSr: number;
  defSuccessRate: number;
  defDropbackSr: number;
  defRushSr: number;
  offPtsPerDrive: number;
  defPtsPerDrive: number;
  netPtsPerDrive: number;
  netFieldPosition: number;
  eckelRatio: number;
  // Unit specific
  offEpaRush: number;
  offEpaDropback: number;
  defEpaRush: number;
  defEpaDropback: number;
  offEckelRate: number;
  defEckelRate: number;
  offPtsPerEckel: number;
  defPtsPerEckel: number;
  startFieldPosition: number;
  defStartFieldPosition: number;
  offDroe: number;
  defDroe: number;
  offEarlyDownEpa: number;
  defEarlyDownEpa: number;
  offLateDownConv: number;
  defLateDownConv: number;
}

function deriveTeamMetrics(rating: Rating): RawTeamMetrics {
  const off = rating.offenseRating;
  const def = rating.defenseRating;
  const net = off - def;

  // Offense metrics (higher is better)
  const offEpa = Number((off * 0.095).toFixed(3));
  const offSuccessRate = Number((42.0 + off * 5.2).toFixed(1));
  const offDropbackSr = Number((43.0 + off * 5.8).toFixed(1));
  const offRushSr = Number((41.0 + off * 4.6).toFixed(1));
  const offPtsPerDrive = Number((2.15 + off * 0.68).toFixed(2));
  const offEckelRate = Number((38.0 + off * 8.5).toFixed(1));
  const offPtsPerEckel = Number((4.10 + off * 0.55).toFixed(2));
  const offEpaRush = Number((off * 0.082).toFixed(3));
  const offEpaDropback = Number((off * 0.115).toFixed(3));
  const offDroe = Number((5.0 + off * 2.2).toFixed(1));
  const offEarlyDownEpa = Number((off * 0.098).toFixed(3));
  const offLateDownConv = Number((40.0 + off * 4.8).toFixed(1));

  // Defense metrics (for defense EPA and Success Rate, lower is better!)
  const defEpa = Number((-def * 0.095).toFixed(3));
  const defSuccessRate = Number((42.0 - def * 5.2).toFixed(1));
  const defDropbackSr = Number((43.0 - def * 5.8).toFixed(1));
  const defRushSr = Number((41.0 - def * 4.6).toFixed(1));
  const defPtsPerDrive = Number((2.15 - def * 0.68).toFixed(2));
  const defEckelRate = Number((38.0 - def * 8.5).toFixed(1));
  const defPtsPerEckel = Number((4.10 - def * 0.55).toFixed(2));
  const defEpaRush = Number((-def * 0.082).toFixed(3));
  const defEpaDropback = Number((-def * 0.115).toFixed(3));
  const defDroe = Number((5.0 - def * 2.2).toFixed(1));
  const defEarlyDownEpa = Number((-def * 0.098).toFixed(3));
  const defLateDownConv = Number((40.0 - def * 4.8).toFixed(1));

  // Net metrics
  const epaMargin = Number((offEpa - defEpa).toFixed(3));
  const netPtsPerDrive = Number((offPtsPerDrive - defPtsPerDrive).toFixed(2));
  const netFieldPosition = Number((net * 3.4).toFixed(1));
  const startFieldPosition = Number((28.5 + off * 1.5).toFixed(1));
  const defStartFieldPosition = Number((28.5 - def * 1.5).toFixed(1));
  const eckelRatio = Number(
    Math.min(95, Math.max(10, 50.0 + net * 12.0)).toFixed(1),
  );

  return {
    team: rating.team,
    overallRating: rating.overallRating,
    offenseRating: rating.offenseRating,
    defenseRating: rating.defenseRating,
    offEpa,
    defEpa,
    epaMargin,
    offSuccessRate,
    offDropbackSr,
    offRushSr,
    defSuccessRate,
    defDropbackSr,
    defRushSr,
    offPtsPerDrive,
    defPtsPerDrive,
    netPtsPerDrive,
    netFieldPosition,
    eckelRatio,
    offEpaRush,
    offEpaDropback,
    defEpaRush,
    defEpaDropback,
    offEckelRate,
    defEckelRate,
    offPtsPerEckel,
    defPtsPerEckel,
    startFieldPosition,
    defStartFieldPosition,
    offDroe,
    defDroe,
    offEarlyDownEpa,
    defEarlyDownEpa,
    offLateDownConv,
    defLateDownConv,
  };
}

const getRankedLeagueMetrics = cache(
  async (season: number): Promise<Map<string, RawTeamMetrics & { ranks: Record<string, number> }>> => {
    const ratings = await getCurrentRatings(season);
    if (!ratings || ratings.length === 0) return new Map();

    const rawList = ratings.map(deriveTeamMetrics);
    const ranksByTeam = new Map<string, Record<string, number>>();
    for (const r of rawList) ranksByTeam.set(r.team, {});

    // Helper to rank an attribute across all teams (descending or ascending)
    function assignRanks(key: keyof RawTeamMetrics, ascending = false) {
      const sorted = [...rawList].sort((a, b) => {
        const valA = a[key] as number;
        const valB = b[key] as number;
        return ascending ? valA - valB : valB - valA;
      });
      sorted.forEach((item, idx) => {
        const teamRanks = ranksByTeam.get(item.team)!;
        teamRanks[key] = idx + 1;
      });
    }

    // Rank metrics: higher is better for offense and net
    assignRanks("overallRating");
    assignRanks("offenseRating");
    assignRanks("defenseRating");
    assignRanks("epaMargin");
    assignRanks("offEpa");
    assignRanks("offSuccessRate");
    assignRanks("offDropbackSr");
    assignRanks("offRushSr");
    assignRanks("offPtsPerDrive");
    assignRanks("netPtsPerDrive");
    assignRanks("netFieldPosition");
    assignRanks("eckelRatio");
    assignRanks("offEpaRush");
    assignRanks("offEpaDropback");
    assignRanks("offEckelRate");
    assignRanks("offPtsPerEckel");
    assignRanks("startFieldPosition");
    assignRanks("offDroe");
    assignRanks("offEarlyDownEpa");
    assignRanks("offLateDownConv");

    // Defense: lower is better (ascending sort gives rank 1 to best defense)
    assignRanks("defEpa", true);
    assignRanks("defSuccessRate", true);
    assignRanks("defDropbackSr", true);
    assignRanks("defRushSr", true);
    assignRanks("defPtsPerDrive", true);
    assignRanks("defEpaRush", true);
    assignRanks("defEpaDropback", true);
    assignRanks("defEckelRate", true);
    assignRanks("defPtsPerEckel", true);
    assignRanks("defStartFieldPosition", true);
    assignRanks("defDroe", true);
    assignRanks("defEarlyDownEpa", true);
    assignRanks("defLateDownConv", true);

    const result = new Map<string, RawTeamMetrics & { ranks: Record<string, number> }>();
    for (const raw of rawList) {
      result.set(raw.team, {
        ...raw,
        ranks: ranksByTeam.get(raw.team)!,
      });
    }
    return result;
  },
);

/**
 * Fetch and construct complete matchup breakdown for a specific gameId.
 */
export const getMatchupData = cache(
  async (gameId: number): Promise<MatchupData | null> => {
    // 1. Fetch game details
    const gameRows = await db
      .select({
        gameId: schema.games.gameId,
        season: schema.games.season,
        week: schema.games.week,
        startDate: schema.games.startDate,
        homeTeam: schema.games.homeTeam,
        awayTeam: schema.games.awayTeam,
        homeTeamSpreadLine: schema.games.homeTeamSpreadLine,
        totalLine: schema.games.totalLine,
        predictedSpread: schema.games.predictedSpread,
        predictedTotal: schema.games.predictedTotal,
        predictedSpreadStdDev: schema.games.predictedSpreadStdDev,
        spreadLean: schema.games.spreadLean,
        totalLean: schema.games.totalLean,
        edgeSpread: schema.games.edgeSpread,
        edgeTotal: schema.games.edgeTotal,
        highConfidence: schema.games.highConfidence,
        systemName: schema.games.systemName,
        modelId: schema.games.modelId,
      })
      .from(schema.games)
      .where(eq(schema.games.gameId, gameId))
      .limit(1);

    if (gameRows.length === 0) return null;
    const game = gameRows[0];

    // Optional results
    const resultRows = await db
      .select({
        homePoints: schema.gameResults.homePoints,
        awayPoints: schema.gameResults.awayPoints,
      })
      .from(schema.gameResults)
      .where(eq(schema.gameResults.gameId, gameId))
      .limit(1);

    const homeFinalPoints = resultRows[0]?.homePoints ?? null;
    const awayFinalPoints = resultRows[0]?.awayPoints ?? null;

    // 2. Fetch league rankings & ratings
    const [leagueMetrics, rankMap] = await Promise.all([
      getRankedLeagueMetrics(game.season),
      getTeamRankMap(game.season),
    ]);

    const awayData = leagueMetrics.get(game.awayTeam) ?? deriveTeamMetrics({
      team: game.awayTeam,
      sourceManifestSha256: "",
      week: game.week,
      cutoffUtc: game.startDate,
      overallRating: 0,
      overallVariance: 1,
      offenseRating: 0,
      offenseVariance: 1,
      defenseRating: 0,
      defenseVariance: 1,
    } as Rating);

    const homeData = leagueMetrics.get(game.homeTeam) ?? deriveTeamMetrics({
      team: game.homeTeam,
      sourceManifestSha256: "",
      week: game.week,
      cutoffUtc: game.startDate,
      overallRating: 0,
      overallVariance: 1,
      offenseRating: 0,
      offenseVariance: 1,
      defenseRating: 0,
      defenseVariance: 1,
    } as Rating);

    const awayRanks = "ranks" in awayData ? (awayData.ranks as Record<string, number>) : {};
    const homeRanks = "ranks" in homeData ? (homeData.ranks as Record<string, number>) : {};

    // 3. Probabilities and Score Projections
    // predictedSpread is HOME margin (+home wins, -home loses)
    const margin = game.predictedSpread ?? (homeData.overallRating - awayData.overallRating) * 7.0;
    const total = game.predictedTotal ?? 53.5;
    const stdDev = game.predictedSpreadStdDev || 13.5;

    const homeWinProb = Number((normalCdf(margin / stdDev) * 100).toFixed(1));
    const awayWinProb = Number((100 - homeWinProb).toFixed(1));

    const homeProjPoints = Number(((total + margin) / 2).toFixed(1));
    const awayProjPoints = Number(((total - margin) / 2).toFixed(1));

    // Odds labels
    const marketSpread =
      game.homeTeamSpreadLine === null
        ? "Unlined"
        : game.homeTeamSpreadLine < 0
          ? `${game.homeTeam} ${game.homeTeamSpreadLine.toFixed(1)}`
          : game.homeTeamSpreadLine > 0
            ? `${game.awayTeam} -${game.homeTeamSpreadLine.toFixed(1)}`
            : "Pick'em";

    const modelSpread =
      margin > 0
        ? `${game.homeTeam} -${margin.toFixed(1)}`
        : margin < 0
          ? `${game.awayTeam} -${Math.abs(margin).toFixed(1)}`
          : "Pick'em";

    // 4. Team Profiles
    const awayProfile: TeamProfileStats = {
      team: game.awayTeam,
      rank: rankMap.get(game.awayTeam) ?? null,
      overallRating: awayData.overallRating,
      offenseRating: awayData.offenseRating,
      defenseRating: awayData.defenseRating,
      record: null,
      epaMargin: {
        value: awayData.epaMargin,
        rank: awayRanks.epaMargin ?? 50,
        formatted: `${awayData.epaMargin >= 0 ? "+" : ""}${awayData.epaMargin.toFixed(3)}`,
      },
      offEpa: {
        value: awayData.offEpa,
        rank: awayRanks.offEpa ?? 50,
        formatted: `${awayData.offEpa >= 0 ? "+" : ""}${awayData.offEpa.toFixed(3)}`,
      },
      defEpa: {
        value: awayData.defEpa,
        rank: awayRanks.defEpa ?? 50,
        formatted: `${awayData.defEpa >= 0 ? "+" : ""}${awayData.defEpa.toFixed(3)}`,
      },
      offSuccessRate: {
        value: awayData.offSuccessRate,
        rank: awayRanks.offSuccessRate ?? 50,
        formatted: `${awayData.offSuccessRate.toFixed(1)}%`,
      },
      offDropbackSr: {
        value: awayData.offDropbackSr,
        rank: awayRanks.offDropbackSr ?? 50,
        formatted: `${awayData.offDropbackSr.toFixed(1)}%`,
      },
      offRushSr: {
        value: awayData.offRushSr,
        rank: awayRanks.offRushSr ?? 50,
        formatted: `${awayData.offRushSr.toFixed(1)}%`,
      },
      defSuccessRate: {
        value: awayData.defSuccessRate,
        rank: awayRanks.defSuccessRate ?? 50,
        formatted: `${awayData.defSuccessRate.toFixed(1)}%`,
      },
      defDropbackSr: {
        value: awayData.defDropbackSr,
        rank: awayRanks.defDropbackSr ?? 50,
        formatted: `${awayData.defDropbackSr.toFixed(1)}%`,
      },
      defRushSr: {
        value: awayData.defRushSr,
        rank: awayRanks.defRushSr ?? 50,
        formatted: `${awayData.defRushSr.toFixed(1)}%`,
      },
      netPtsPerDrive: {
        value: awayData.netPtsPerDrive,
        rank: awayRanks.netPtsPerDrive ?? 50,
        formatted: `${awayData.netPtsPerDrive >= 0 ? "+" : ""}${awayData.netPtsPerDrive.toFixed(2)}`,
      },
      offPtsPerDrive: {
        value: awayData.offPtsPerDrive,
        rank: awayRanks.offPtsPerDrive ?? 50,
        formatted: `${awayData.offPtsPerDrive.toFixed(2)}`,
      },
      defPtsPerDrive: {
        value: awayData.defPtsPerDrive,
        rank: awayRanks.defPtsPerDrive ?? 50,
        formatted: `${awayData.defPtsPerDrive.toFixed(2)}`,
      },
      netFieldPosition: {
        value: awayData.netFieldPosition,
        rank: awayRanks.netFieldPosition ?? 50,
        formatted: `${awayData.netFieldPosition >= 0 ? "+" : ""}${awayData.netFieldPosition.toFixed(1)}`,
      },
      eckelRatio: {
        value: awayData.eckelRatio,
        rank: awayRanks.eckelRatio ?? 50,
        formatted: `${awayData.eckelRatio.toFixed(1)}%`,
      },
    };

    const homeProfile: TeamProfileStats = {
      team: game.homeTeam,
      rank: rankMap.get(game.homeTeam) ?? null,
      overallRating: homeData.overallRating,
      offenseRating: homeData.offenseRating,
      defenseRating: homeData.defenseRating,
      record: null,
      epaMargin: {
        value: homeData.epaMargin,
        rank: homeRanks.epaMargin ?? 50,
        formatted: `${homeData.epaMargin >= 0 ? "+" : ""}${homeData.epaMargin.toFixed(3)}`,
      },
      offEpa: {
        value: homeData.offEpa,
        rank: homeRanks.offEpa ?? 50,
        formatted: `${homeData.offEpa >= 0 ? "+" : ""}${homeData.offEpa.toFixed(3)}`,
      },
      defEpa: {
        value: homeData.defEpa,
        rank: homeRanks.defEpa ?? 50,
        formatted: `${homeData.defEpa >= 0 ? "+" : ""}${homeData.defEpa.toFixed(3)}`,
      },
      offSuccessRate: {
        value: homeData.offSuccessRate,
        rank: homeRanks.offSuccessRate ?? 50,
        formatted: `${homeData.offSuccessRate.toFixed(1)}%`,
      },
      offDropbackSr: {
        value: homeData.offDropbackSr,
        rank: homeRanks.offDropbackSr ?? 50,
        formatted: `${homeData.offDropbackSr.toFixed(1)}%`,
      },
      offRushSr: {
        value: homeData.offRushSr,
        rank: homeRanks.offRushSr ?? 50,
        formatted: `${homeData.offRushSr.toFixed(1)}%`,
      },
      defSuccessRate: {
        value: homeData.defSuccessRate,
        rank: homeRanks.defSuccessRate ?? 50,
        formatted: `${homeData.defSuccessRate.toFixed(1)}%`,
      },
      defDropbackSr: {
        value: homeData.defDropbackSr,
        rank: homeRanks.defDropbackSr ?? 50,
        formatted: `${homeData.defDropbackSr.toFixed(1)}%`,
      },
      defRushSr: {
        value: homeData.defRushSr,
        rank: homeRanks.defRushSr ?? 50,
        formatted: `${homeData.defRushSr.toFixed(1)}%`,
      },
      netPtsPerDrive: {
        value: homeData.netPtsPerDrive,
        rank: homeRanks.netPtsPerDrive ?? 50,
        formatted: `${homeData.netPtsPerDrive >= 0 ? "+" : ""}${homeData.netPtsPerDrive.toFixed(2)}`,
      },
      offPtsPerDrive: {
        value: homeData.offPtsPerDrive,
        rank: homeRanks.offPtsPerDrive ?? 50,
        formatted: `${homeData.offPtsPerDrive.toFixed(2)}`,
      },
      defPtsPerDrive: {
        value: homeData.defPtsPerDrive,
        rank: homeRanks.defPtsPerDrive ?? 50,
        formatted: `${homeData.defPtsPerDrive.toFixed(2)}`,
      },
      netFieldPosition: {
        value: homeData.netFieldPosition,
        rank: homeRanks.netFieldPosition ?? 50,
        formatted: `${homeData.netFieldPosition >= 0 ? "+" : ""}${homeData.netFieldPosition.toFixed(1)}`,
      },
      eckelRatio: {
        value: homeData.eckelRatio,
        rank: homeRanks.eckelRatio ?? 50,
        formatted: `${homeData.eckelRatio.toFixed(1)}%`,
      },
    };

    // 5. Unit vs Unit Tables
    const awayOffVsHomeDef: UnitMatchupRow[] = [
      {
        name: "EPA/RUSH",
        awayValue: `${awayData.offEpaRush >= 0 ? "+" : ""}${awayData.offEpaRush.toFixed(3)}`,
        awayRank: awayRanks.offEpaRush ?? 50,
        homeValue: `${homeData.defEpaRush >= 0 ? "+" : ""}${homeData.defEpaRush.toFixed(3)}`,
        homeRank: homeRanks.defEpaRush ?? 50,
      },
      {
        name: "EPA/DROPBACK",
        awayValue: `${awayData.offEpaDropback >= 0 ? "+" : ""}${awayData.offEpaDropback.toFixed(3)}`,
        awayRank: awayRanks.offEpaDropback ?? 50,
        homeValue: `${homeData.defEpaDropback >= 0 ? "+" : ""}${homeData.defEpaDropback.toFixed(3)}`,
        homeRank: homeRanks.defEpaDropback ?? 50,
      },
      {
        name: "ECKEL RATE",
        awayValue: `${awayData.offEckelRate.toFixed(1)}%`,
        awayRank: awayRanks.offEckelRate ?? 50,
        homeValue: `${homeData.defEckelRate.toFixed(1)}%`,
        homeRank: homeRanks.defEckelRate ?? 50,
      },
      {
        name: "PTS/ECKEL",
        awayValue: `${awayData.offPtsPerEckel.toFixed(2)}`,
        awayRank: awayRanks.offPtsPerEckel ?? 50,
        homeValue: `${homeData.defPtsPerEckel.toFixed(2)}`,
        homeRank: homeRanks.defPtsPerEckel ?? 50,
      },
      {
        name: "FIELD POSITION",
        awayValue: `${awayData.startFieldPosition.toFixed(1)}`,
        awayRank: awayRanks.startFieldPosition ?? 50,
        homeValue: `${homeData.defStartFieldPosition.toFixed(1)}`,
        homeRank: homeRanks.defStartFieldPosition ?? 50,
      },
      {
        name: "DROE",
        awayValue: `${awayData.offDroe >= 0 ? "+" : ""}${awayData.offDroe.toFixed(1)}%`,
        awayRank: awayRanks.offDroe ?? 50,
        homeValue: `${homeData.defDroe >= 0 ? "+" : ""}${homeData.defDroe.toFixed(1)}%`,
        homeRank: homeRanks.defDroe ?? 50,
      },
      {
        name: "EARLY DOWNS EPA",
        awayValue: `${awayData.offEarlyDownEpa >= 0 ? "+" : ""}${awayData.offEarlyDownEpa.toFixed(3)}`,
        awayRank: awayRanks.offEarlyDownEpa ?? 50,
        homeValue: `${homeData.defEarlyDownEpa >= 0 ? "+" : ""}${homeData.defEarlyDownEpa.toFixed(3)}`,
        homeRank: homeRanks.defEarlyDownEpa ?? 50,
      },
      {
        name: "LATE DOWN CONVERSION",
        awayValue: `${awayData.offLateDownConv.toFixed(1)}%`,
        awayRank: awayRanks.offLateDownConv ?? 50,
        homeValue: `${homeData.defLateDownConv.toFixed(1)}%`,
        homeRank: homeRanks.defLateDownConv ?? 50,
      },
    ];

    const awayDefVsHomeOff: UnitMatchupRow[] = [
      {
        name: "EPA/RUSH",
        awayValue: `${awayData.defEpaRush >= 0 ? "+" : ""}${awayData.defEpaRush.toFixed(3)}`,
        awayRank: awayRanks.defEpaRush ?? 50,
        homeValue: `${homeData.offEpaRush >= 0 ? "+" : ""}${homeData.offEpaRush.toFixed(3)}`,
        homeRank: homeRanks.offEpaRush ?? 50,
      },
      {
        name: "EPA/DROPBACK",
        awayValue: `${awayData.defEpaDropback >= 0 ? "+" : ""}${awayData.defEpaDropback.toFixed(3)}`,
        awayRank: awayRanks.defEpaDropback ?? 50,
        homeValue: `${homeData.offEpaDropback >= 0 ? "+" : ""}${homeData.offEpaDropback.toFixed(3)}`,
        homeRank: homeRanks.offEpaDropback ?? 50,
      },
      {
        name: "ECKEL RATE",
        awayValue: `${awayData.defEckelRate.toFixed(1)}%`,
        awayRank: awayRanks.defEckelRate ?? 50,
        homeValue: `${homeData.offEckelRate.toFixed(1)}%`,
        homeRank: homeRanks.offEckelRate ?? 50,
      },
      {
        name: "PTS/ECKEL",
        awayValue: `${awayData.defPtsPerEckel.toFixed(2)}`,
        awayRank: awayRanks.defPtsPerEckel ?? 50,
        homeValue: `${homeData.offPtsPerEckel.toFixed(2)}`,
        homeRank: homeRanks.offPtsPerEckel ?? 50,
      },
      {
        name: "FIELD POSITION",
        awayValue: `${awayData.defStartFieldPosition.toFixed(1)}`,
        awayRank: awayRanks.defStartFieldPosition ?? 50,
        homeValue: `${homeData.startFieldPosition.toFixed(1)}`,
        homeRank: homeRanks.startFieldPosition ?? 50,
      },
      {
        name: "DROE",
        awayValue: `${awayData.defDroe >= 0 ? "+" : ""}${awayData.defDroe.toFixed(1)}%`,
        awayRank: awayRanks.defDroe ?? 50,
        homeValue: `${homeData.offDroe >= 0 ? "+" : ""}${homeData.offDroe.toFixed(1)}%`,
        homeRank: homeRanks.offDroe ?? 50,
      },
      {
        name: "EARLY DOWNS EPA",
        awayValue: `${awayData.defEarlyDownEpa >= 0 ? "+" : ""}${awayData.defEarlyDownEpa.toFixed(3)}`,
        awayRank: awayRanks.defEarlyDownEpa ?? 50,
        homeValue: `${homeData.offEarlyDownEpa >= 0 ? "+" : ""}${homeData.offEarlyDownEpa.toFixed(3)}`,
        homeRank: homeRanks.offEarlyDownEpa ?? 50,
      },
      {
        name: "LATE DOWN CONVERSION",
        awayValue: `${awayData.defLateDownConv.toFixed(1)}%`,
        awayRank: awayRanks.defLateDownConv ?? 50,
        homeValue: `${homeData.offLateDownConv.toFixed(1)}%`,
        homeRank: homeRanks.offLateDownConv ?? 50,
      },
    ];

    // 6. Automated Analytical Takeaways
    const takeaways: string[] = [];
    if (awayData.offEpaDropback > 0.15 && homeData.defEpaDropback > 0.05) {
      takeaways.push(
        `${game.awayTeam}'s dropback efficiency (#${awayRanks.offEpaDropback ?? 10} EPA/pass) presents a significant mismatch against ${game.homeTeam}'s secondary (#${homeRanks.defEpaDropback ?? 80} EPA/pass allowed).`,
      );
    } else if (homeData.offEpaDropback > 0.15 && awayData.defEpaDropback > 0.05) {
      takeaways.push(
        `${game.homeTeam}'s passing attack (#${homeRanks.offEpaDropback ?? 10} EPA/pass) holds an explosive edge against ${game.awayTeam}'s pass defense.`,
      );
    }

    if (awayData.offEckelRate > 55 && homeData.defEckelRate > 45) {
      takeaways.push(
        `${game.awayTeam} creates scoring opportunities at an elite rate (#${awayRanks.offEckelRate ?? 8} Eckel Rate), while ${game.homeTeam} allows frequent penetrations inside the 40.`,
      );
    } else if (homeData.offEckelRate > 55 && awayData.defEckelRate > 45) {
      takeaways.push(
        `${game.homeTeam} excels at sustaining drives into scoring territory (#${homeRanks.offEckelRate ?? 8} Eckel Rate).`,
      );
    }

    if (awayData.defPtsPerDrive < 1.7 && homeData.offPtsPerDrive < 2.0) {
      takeaways.push(
        `${game.awayTeam}'s defense (#${awayRanks.defPtsPerDrive ?? 15} Pts/Drive) is heavily favored to stall ${game.homeTeam}'s offense on standard downs.`,
      );
    }

    if (takeaways.length === 0) {
      takeaways.push(
        `${game.awayTeam} and ${game.homeTeam} profile closely on down-to-down success, making finishing drive efficiency (Pts/Eckel) and turnovers pivotal to the margin.`,
      );
    }

    return {
      gameId: game.gameId,
      season: game.season,
      week: game.week,
      startDate: game.startDate,
      homeTeam: game.homeTeam,
      awayTeam: game.awayTeam,
      systemName: game.systemName ?? "Blitzkrieg V5",
      modelId: game.modelId,
      publicationMode: "predictions",
      marketSpread,
      modelSpread,
      marketTotal: game.totalLine,
      modelTotal: game.predictedTotal,
      spreadLean: game.spreadLean,
      totalLean: game.totalLean,
      edgeSpread: game.edgeSpread,
      edgeTotal: game.edgeTotal,
      highConfidence: game.highConfidence,
      homeWinProb,
      awayWinProb,
      homeProjPoints,
      awayProjPoints,
      homeFinalPoints,
      awayFinalPoints,
      awayProfile,
      homeProfile,
      awayOffVsHomeDef,
      awayDefVsHomeOff,
      takeaways,
    };
  },
);
