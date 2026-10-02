import type { MatchupData, TeamRatingSummary } from "@/lib/matchup";
import { marketSpreadView, modelSpreadView, spreadEdge, spreadLabel, totalEdge } from "@/lib/betting-format";
import { UNIT_METRICS, buildMatchupStats, type TeamStatRow } from "@/lib/team-stats";
import { protoGames, protoResultGames } from "./slate";

function hash(text: string): number {
  let h = 17;
  for (const ch of text) h = (h * 31 + ch.charCodeAt(0)) % 9973;
  return h;
}

/**
 * Deterministic fixture stats (test mode only). The away team has no national
 * rank on explosive plays and pass EPA (unranked rows), and the home defense
 * has an exact-zero explosive rate (a value with no rank); every other row is
 * ranked, with a few ties.
 */
function fixtureRows(teams: string[], unrankedTeam: string): TeamStatRow[] {
  const rows: TeamStatRow[] = [];
  for (const team of teams) {
    for (const role of ["offense", "defense"] as const) {
      UNIT_METRICS.forEach((m, i) => {
        const seed = hash(`${team}|${role}|${m.key}`);
        const frac = (seed % 1000) / 1000;
        const value =
          m.format === "epa" ? frac * 0.6 - 0.3
          : m.format === "pct" ? 0.25 + frac * 0.3
          : m.format === "pts" ? 3 + frac * 2
          : 25 + frac * 12;
        const unranked =
          team === unrankedTeam && (m.key === "explosive_rate" || m.key === "epa_pass");
        const zero = team !== unrankedTeam && role === "defense" && m.key === "explosive_rate";
        const rank = unranked ? null : 1 + ((seed + i) % 134);
        rows.push({
          team,
          role,
          metric: m.key,
          value: zero ? 0 : value,
          n: 120,
          games: 4,
          rank,
          cohortSize: unranked ? null : 134,
          // A few deterministic ties so the "T-" label is exercised.
          tied: rank !== null && rank % 11 === 0,
        });
      });
    }
  }
  return rows;
}

function rating(team: string, rank: number): TeamRatingSummary {
  return {
    team,
    rank,
    overallRating: 5 - rank / 10,
    offenseRating: 2,
    offenseRank: rank,
    defenseRating: 1,
    defenseRank: rank + 3,
  };
}

export function fixtureMatchup(gameId: number): MatchupData | null {
  const game = [...protoGames(), ...protoResultGames()].find((g) => g.gameId === gameId);
  if (!game) return null;
  const predictions = game.publicationMode === "predictions";
  const marketView = marketSpreadView(game.homeTeam, game.awayTeam, game.homeTeamSpreadLine);
  const modelView = modelSpreadView(
    game.homeTeam,
    game.awayTeam,
    predictions ? game.predictedSpread : null,
  );
  const rows = fixtureRows([game.homeTeam, game.awayTeam], game.awayTeam);
  return {
    gameId: game.gameId,
    season: game.season,
    week: game.week,
    startDate: game.startDate,
    updatedAt: new Date("2026-09-30T03:24:00.000Z"),
    homeTeam: game.homeTeam,
    awayTeam: game.awayTeam,
    homeRecord: game.homeRecord,
    awayRecord: game.awayRecord,
    venueCity: game.venueCity ?? null,
    venueState: game.venueState ?? null,
    neutralSite: game.neutralSite ?? null,
    systemName: predictions ? "Blitzkrieg" : null,
    modelId: predictions ? game.modelId : null,
    publicationMode: predictions ? "predictions" : "market",
    marketSpread: spreadLabel(marketView),
    modelSpread: spreadLabel(modelView),
    marketTotal: game.totalLine,
    modelTotal: predictions ? game.predictedTotal : null,
    spreadLean: predictions ? game.spreadLean : null,
    totalLean: predictions ? game.totalLean : null,
    edgeSpread: predictions ? game.edgeSpread : null,
    edgeTotal: predictions ? game.edgeTotal : null,
    modelSpreadEdge: predictions ? spreadEdge(modelView, marketView) : null,
    modelTotalEdge: predictions ? totalEdge(game.predictedTotal, game.totalLine) : null,
    spreadSource: predictions ? (game.spreadSource ?? null) : null,
    totalSource: predictions ? (game.totalSource ?? null) : null,
    highConfidence: predictions ? game.highConfidence : false,
    homeFinalPoints: game.homePoints,
    awayFinalPoints: game.awayPoints,
    awayRating: rating(game.awayTeam, 12),
    homeRating: rating(game.homeTeam, 30),
    stats: buildMatchupStats(rows, game.week, game.awayTeam, game.homeTeam),
  };
}
