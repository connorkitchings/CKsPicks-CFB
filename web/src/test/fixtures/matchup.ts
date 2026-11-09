import type { MatchupData, TeamRatingSummary } from "@/lib/matchup";
import { marketSpreadView, modelSpreadView, spreadEdge, spreadLabel, totalEdge } from "@/lib/betting-format";
import { UNIT_METRICS, buildMatchupStats, type TeamStatRow } from "@/lib/team-stats";
import {
  buildUnitBreakdown,
  componentId,
  type ComponentRow,
  type RatingBreakdown,
  type ScheduledGame,
  type UnitRole,
} from "@/lib/rating-breakdown";
import { protoGames, protoResultGames } from "./slate";

function hash(text: string): number {
  let h = 17;
  for (const ch of text) h = (h * 31 + ch.charCodeAt(0)) % 9973;
  return h;
}

/**
 * Deterministic fixture stats (test mode only). The away team has no national
 * rank on explosive plays and pass PPA (unranked rows), and the home defense
 * has an exact-zero explosive rate (a value with no rank); every other row is
 * ranked, with a few ties.
 */
export function fixtureRows(teams: string[], unrankedTeam: string): TeamStatRow[] {
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

export type BreakdownFixtureMode = "default" | "mismatch" | "preseason";

const FIXTURE_SOURCE = "f".repeat(64);

/** Synthetic component rows, run through the real builder. Prior share is 20% (preseason: 100%). */
export function fixtureBreakdown(
  awayTeam: string,
  homeTeam: string,
  mode: BreakdownFixtureMode = "default",
): RatingBreakdown {
  const schedule = new Map<number, ScheduledGame>();
  const components = new Map<string, ComponentRow>();
  const units = [[awayTeam, 1, 12, 15], [homeTeam, 2, 30, 33]] as const;

  function unit(team: string, base: number, role: UnitRole, rank: number, withExtras: boolean) {
    const rating = role === "offense" ? 2 : 1;
    const snapshotId = `fixture:${team}`;
    const games = mode === "preseason" ? [] : [
      { id: base + 1, week: 1, exposure: 20, raw: 3.0, adjusted: 3.4, share: 0.5, home: true, other: "Rice" },
      { id: base + 2, week: 2, exposure: 25, raw: 3.3, adjusted: 3.6, share: 0.3, home: false, other: "Memphis" },
      { id: base + 3, week: 3, exposure: 14, raw: 3.5, adjusted: 3.5, share: 0.2, home: true, other: "Tulane" },
    ];
    const prior = mode === "preseason" ? 1 : 0.2;
    for (const game of games) {
      schedule.set(game.id, game.home
        ? { week: game.week, homeTeam: team, awayTeam: game.other }
        : { week: game.week, homeTeam: game.other, awayTeam: team });
    }
    schedule.set(base + 4, { week: 4, homeTeam: team, awayTeam: "Navy" });
    const evidence = games.map((game) => ({
      game_id: game.id,
      source_week: game.week,
      exposure: game.exposure,
      raw_ppp: game.raw,
      adjusted_ppp: game.adjusted,
      adjusted_z: 0,
      contribution: rating * (1 - prior) * game.share,
      // The third game of the first unit has no opponent context.
      missing_context_reason: withExtras && game.id === base + 3 ? "missing_opponent_context_raw_ppp" : null,
    }));
    const row: ComponentRow = {
      componentId: componentId(snapshotId, role),
      v5SnapshotId: snapshotId,
      sourceManifestSha256: FIXTURE_SOURCE,
      ratingTeam: team,
      unitRole: role,
      ratingMean: rating + (mode === "mismatch" && team === homeTeam && role === "defense" ? 0.01 : 0),
      priorWeight: prior,
      priorContribution: rating * prior,
      usableExposure: games.reduce((sum, game) => sum + game.exposure, 0),
      completedGames: games.length,
      evidence,
      excludedObservations: withExtras && mode === "default"
        ? [{ game_id: base + 4, week: 4, reason: "unresolved_scoring_attribution" }]
        : [],
    };
    components.set(row.componentId, row);
    return { role, team, rank, rating, snapshotId };
  }

  const built = units.flatMap(([team, base, offenseRank, defenseRank]) => [
    unit(team, base * 100, "offense", offenseRank, team === awayTeam),
    unit(team, base * 100, "defense", defenseRank, false),
  ]);
  const [awayOffense, awayDefense, homeOffense, homeDefense] = built.map(({ role, team, rank, rating, snapshotId }) =>
    buildUnitBreakdown({
      role,
      team,
      rendered: { snapshotId, sourceManifestSha256: FIXTURE_SOURCE, ratingTeam: team, rating, rank },
      components,
      schedule,
    }));
  return { awayOffense, awayDefense, homeOffense, homeDefense };
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
    marketSpreadLine: game.homeTeamSpreadLine,
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
    spreadResult: predictions ? (game.spreadResult ?? null) : null,
    totalResult: predictions ? (game.totalResult ?? null) : null,
    awayRating: rating(game.awayTeam, 12),
    homeRating: rating(game.homeTeam, 30),
    stats: buildMatchupStats(rows, game.week, game.awayTeam, game.homeTeam),
    statsUnavailable: false,
    lineageStatus: "ready",
    lineageReason: "Fixture publication provenance agrees.",
    ratingBreakdown: fixtureBreakdown(game.awayTeam, game.homeTeam),
  };
}

/**
 * Test-only game id whose stored stat rows "broke their contract": the page must show
 * the unavailable state, not the "not published" copy and not partial numbers.
 */
export const STATS_CONTRACT_VIOLATION_GAME_ID = 987655;
export const LINEAGE_MISMATCH_GAME_ID = 987656;
/** Test-only: the home defense's stored rating is off by 0.01, so that one card is unavailable. */
export const RATING_BREAKDOWN_MISMATCH_GAME_ID = 987657;
/** Test-only: all four units are preseason-only (no completed games). */
export const PRESEASON_BREAKDOWN_GAME_ID = 987658;

export function fixtureMatchupForId(gameId: number): MatchupData | null {
  const breakdownMode: BreakdownFixtureMode | null =
    gameId === RATING_BREAKDOWN_MISMATCH_GAME_ID ? "mismatch"
    : gameId === PRESEASON_BREAKDOWN_GAME_ID ? "preseason"
    : null;
  if (breakdownMode) {
    const base = fixtureMatchup(1);
    return base
      ? { ...base, gameId, ratingBreakdown: fixtureBreakdown(base.awayTeam, base.homeTeam, breakdownMode) }
      : null;
  }
  if (gameId === LINEAGE_MISMATCH_GAME_ID) {
    const base = fixtureMatchup(1);
    return base
      ? { ...base, gameId, stats: null, lineageStatus: "unavailable", lineageReason: "Fixture lineage mismatch." }
      : null;
  }
  if (gameId === STATS_CONTRACT_VIOLATION_GAME_ID) {
    const base = fixtureMatchup(1);
    return base ? { ...base, gameId, stats: null, statsUnavailable: true } : null;
  }
  return fixtureMatchup(gameId);
}
