import { and, asc, desc, eq, inArray, lt, or, sql } from "drizzle-orm";
import { cache } from "react";
import { db, schema } from "./db";
import { withGameNameAliases } from "./rating-names.ts";
import {
  defaultPeriodForRows,
  formatCutoffLabel,
  ownerSourceForCutoff,
  parseSourceQualifiedPeriodId,
  periodBeforeKickoff,
  PRESEASON_META,
  sourceQualifiedPeriodId,
  WEEK_GENERATIONS,
  type PeriodMeta,
  type Rating,
  type RatingPeriod,
} from "./rating-periods.ts";

export type { PeriodMeta, Rating, RatingPeriod };
export {
  defaultPeriodForRows,
  formatCutoffLabel,
  ownerSourceForCutoff,
  PRESEASON_META,
  WEEK_GENERATIONS,
};

const getSelectedRatingSource = cache(async (season: number): Promise<string | null> => {
  const rows = await db.select({ sha: schema.predictionRuns.ratingManifestSha256 })
    .from(schema.siteWeekSelections)
    .innerJoin(schema.predictionRuns, eq(schema.siteWeekSelections.runId, schema.predictionRuns.runId))
    .where(and(
      eq(schema.siteWeekSelections.season, season),
      inArray(schema.predictionRuns.evidenceClass, ["pending", "replay", "live"]),
    ))
    .orderBy(desc(schema.siteWeekSelections.week)).limit(1);
  return rows[0]?.sha ?? null;
});

export const getCurrentRatings = cache(async (season: number): Promise<Rating[]> => {
  const sourceSha = await getSelectedRatingSource(season);
  if (!sourceSha) return [];
  const rows = await db.select({
    team: schema.v5RatingSnapshots.team,
    sourceManifestSha256: schema.v5RatingSnapshots.sourceManifestSha256,
    week: schema.v5RatingSnapshots.week,
    cutoffUtc: schema.v5RatingSnapshots.cutoffUtc,
    offenseRating: schema.v5RatingSnapshots.offenseRating,
    offenseVariance: schema.v5RatingSnapshots.offenseVariance,
    defenseRating: schema.v5RatingSnapshots.defenseRating,
    defenseVariance: schema.v5RatingSnapshots.defenseVariance,
    overallRating: schema.v5RatingSnapshots.overallRating,
    overallVariance: schema.v5RatingSnapshots.overallVariance,
    fallbackReason: schema.v5RatingSnapshots.fallbackReason,
  }).from(schema.v5RatingSnapshots)
    .where(and(
      eq(schema.v5RatingSnapshots.season, season),
      eq(schema.v5RatingSnapshots.sourceManifestSha256, sourceSha),
      eq(schema.v5RatingSnapshots.snapshotClass, "current"),
      sql`${schema.v5RatingSnapshots.cutoffUtc} = (
        SELECT MAX(cutoff_utc) FROM v5_rating_snapshots
        WHERE season = ${season} AND snapshot_class = 'current'
          AND source_manifest_sha256 = ${sourceSha}
      )`,
    ))
    .orderBy(desc(schema.v5RatingSnapshots.createdAt));
  const byTeam = new Map<string, Rating>();
  for (const row of rows) if (!byTeam.has(row.team)) byTeam.set(row.team, row);
  return [...byTeam.values()].sort((a, b) => b.overallRating - a.overallRating);
});

/**
 * Ratings known before a game kicked off: the latest frozen generation at or
 * before kickoff, with teams that had not played yet backfilled from the
 * preseason priors (via `getWeeklyRatings`). Week 0 uses the preseason priors.
 */
export const getRatingsAsOf = cache(async (season: number, kickoffMs: number): Promise<Rating[]> => {
  const period = periodBeforeKickoff(await getRatingPeriods(season), new Date(kickoffMs));
  const { ratings } = await getWeeklyRatings(season, period ? period.id : "preseason");
  return ratings;
});

/**
 * Cached map of team name -> rank (1..134) based on current certified ratings.
 */
export const getTeamRankMap = cache(async (season: number): Promise<Map<string, number>> => {
  const ratings = await getCurrentRatings(season);
  const map = new Map<string, number>();
  ratings.forEach((r, idx) => {
    map.set(r.team, idx + 1);
  });
  for (const [name, rank] of Object.entries(withGameNameAliases(Object.fromEntries(map)))) {
    map.set(name, rank);
  }
  return map;
});

/**
 * Ratings timeline derived from the data, not from hardcoded weeks. Every
 * frozen `current`-class generation is one entry addressable by its exact
 * evidence cutoff; the newest entry is the active model state. New weekly
 * projections appear here with no code change, and past generations can
 * never drift: each one is served from its own frozen rows.
 */
export const getRatingPeriods = cache(async (season: number): Promise<PeriodMeta[]> => {
  const sourceSha = await getSelectedRatingSource(season);
  if (!sourceSha) return [PRESEASON_META];
  const rows = await db.selectDistinct({ cutoffUtc: schema.v5RatingSnapshots.cutoffUtc })
    .from(schema.v5RatingSnapshots)
    .where(and(
      eq(schema.v5RatingSnapshots.season, season),
      eq(schema.v5RatingSnapshots.snapshotClass, "current"),
      eq(schema.v5RatingSnapshots.sourceManifestSha256, sourceSha),
    ))
    .orderBy(desc(schema.v5RatingSnapshots.cutoffUtc));
  const periods = rows.map(({ cutoffUtc }, index) => {
    const iso = cutoffUtc.toISOString();
    const known = WEEK_GENERATIONS[iso];
    const { label: dateLabel, shortLabel: dateShort } = formatCutoffLabel(cutoffUtc);
    const active = index === 0;
    return {
      id: sourceQualifiedPeriodId(sourceSha, cutoffUtc),
      label: known ? `Post-Week ${known.postWeek}` : dateLabel,
      shortLabel: known ? `Week ${known.postWeek}` : dateShort,
      description: known
        ? `Frozen ratings after Week ${known.postWeek} games finalized (${known.games} games, weeks ${known.weeks})${active ? " (active model state)." : "."}`
        : active
          ? "Frozen team ratings from all evidence available at cutoff (active model state)."
          : "Frozen team ratings from all evidence available at cutoff.",
      cutoffUtc,
      sourceManifestSha256: sourceSha,
      ...(known ? { postWeek: known.postWeek } : {}),
    } satisfies PeriodMeta;
  });
  return [...periods, PRESEASON_META];
});

const RATING_SELECT = {
  team: schema.v5RatingSnapshots.team,
  sourceManifestSha256: schema.v5RatingSnapshots.sourceManifestSha256,
  week: schema.v5RatingSnapshots.week,
  cutoffUtc: schema.v5RatingSnapshots.cutoffUtc,
  offenseRating: schema.v5RatingSnapshots.offenseRating,
  offenseVariance: schema.v5RatingSnapshots.offenseVariance,
  defenseRating: schema.v5RatingSnapshots.defenseRating,
  defenseVariance: schema.v5RatingSnapshots.defenseVariance,
  overallRating: schema.v5RatingSnapshots.overallRating,
  overallVariance: schema.v5RatingSnapshots.overallVariance,
  fallbackReason: schema.v5RatingSnapshots.fallbackReason,
};

async function getPreseasonPriors(season: number, sourceSha?: string | null): Promise<Rating[]> {
  // `undefined` preserves the preseason tab's "active model state" meaning via
  // the selected source. An explicit `null` means no owning source was found:
  // return no priors so frozen tabs degrade to frozen-rows-only (fail closed).
  if (sourceSha === null) return [];
  const sha = sourceSha ?? (await getSelectedRatingSource(season));
  if (!sha) return [];
  return db.select(RATING_SELECT).from(schema.v5RatingSnapshots)
    .where(and(
      eq(schema.v5RatingSnapshots.season, season),
      eq(schema.v5RatingSnapshots.sourceManifestSha256, sha),
      sql`${schema.v5RatingSnapshots.snapshotId} LIKE '%:preseason'`,
    ))
    .orderBy(desc(schema.v5RatingSnapshots.overallRating));
}

export const getWeeklyRatings = cache(async (
  season: number,
  targetPeriod?: string | null
): Promise<{ ratings: Rating[]; period: RatingPeriod; periodMeta: PeriodMeta }> => {
  const periods = await getRatingPeriods(season);
  const generations = periods.filter((p) => p.cutoffUtc !== undefined);

  if (targetPeriod === "preseason" || targetPeriod === "pre") {
    const ratings = await getPreseasonPriors(season);
    return { ratings, period: "preseason", periodMeta: PRESEASON_META };
  }

  // Qualified links keep their source forever. Legacy bare-cutoff links bind
  // to the first published source at that cutoff, even after a successor lands.
  const qualified = targetPeriod ? parseSourceQualifiedPeriodId(targetPeriod) : null;
  const legacyCutoff = !qualified && targetPeriod && /^\d{4}-\d{2}-\d{2}T/.test(targetPeriod)
    ? new Date(targetPeriod) : null;
  const frozen = generations.find((p) => p.id === targetPeriod);
  const cutoff = qualified?.cutoff ?? (legacyCutoff && !Number.isNaN(legacyCutoff.getTime()) ? legacyCutoff : frozen?.cutoffUtc);
  if (cutoff) {
    let ownerSource = qualified?.sourceSha ?? frozen?.sourceManifestSha256 ?? null;
    if (!ownerSource) {
      const ownerRows = await db.select({
        sourceManifestSha256: schema.v5RatingSnapshots.sourceManifestSha256,
        createdAt: schema.v5RatingSnapshots.createdAt,
      }).from(schema.v5RatingSnapshots)
        .where(and(
          eq(schema.v5RatingSnapshots.season, season),
          eq(schema.v5RatingSnapshots.snapshotClass, "current"),
          eq(schema.v5RatingSnapshots.cutoffUtc, cutoff),
        ));
      ownerSource = ownerSourceForCutoff(ownerRows);
    }
    if (!ownerSource) return { ratings: [], period: "preseason", periodMeta: PRESEASON_META };
    const rows = await db.select(RATING_SELECT).from(schema.v5RatingSnapshots)
      .where(and(
        eq(schema.v5RatingSnapshots.season, season),
        eq(schema.v5RatingSnapshots.snapshotClass, "current"),
        eq(schema.v5RatingSnapshots.cutoffUtc, cutoff),
        eq(schema.v5RatingSnapshots.sourceManifestSha256, ownerSource),
      ));
    const byTeam = new Map<string, Rating>();
    for (const row of rows) {
      if (!byTeam.has(row.team)) {
        byTeam.set(row.team, row);
      }
    }
    // Early generations cover only teams that had played by the cutoff
    // (post-Week 0: 16 teams). Backfill the rest from preseason priors pinned
    // to the cutoff-owning source, never the currently selected source, so
    // historical tabs stop moving when the site selection changes. An owner
    // without preseason rows degrades to frozen-rows-only (fail closed).
    for (const prior of await getPreseasonPriors(season, ownerSource)) {
      if (!byTeam.has(prior.team)) {
        byTeam.set(prior.team, prior);
      }
    }
    const ratings = [...byTeam.values()].sort((a, b) => b.overallRating - a.overallRating);
    const periodMeta = frozen?.sourceManifestSha256 === ownerSource ? frozen : {
      id: sourceQualifiedPeriodId(ownerSource, cutoff),
      label: WEEK_GENERATIONS[cutoff.toISOString()]
        ? `Post-Week ${WEEK_GENERATIONS[cutoff.toISOString()].postWeek}`
        : formatCutoffLabel(cutoff).label,
      shortLabel: WEEK_GENERATIONS[cutoff.toISOString()]
        ? `Week ${WEEK_GENERATIONS[cutoff.toISOString()].postWeek}`
        : formatCutoffLabel(cutoff).shortLabel,
      description: "Frozen team ratings from this source and exact evidence cutoff.",
      cutoffUtc: cutoff,
      sourceManifestSha256: ownerSource,
    } satisfies PeriodMeta;
    return { ratings, period: periodMeta.id, periodMeta };
  }

  // Retired week-style params ("post-N", "week-N", bare numbers) resolve to
  // the certified generation for that week when one exists, else to latest.
  const weekMatch = targetPeriod?.match(/^(?:post-|week-)?(\d+)$/);
  if (weekMatch) {
    const week = Number(weekMatch[1]);
    const pinned = generations.find((p) => p.postWeek === week);
    if (pinned?.cutoffUtc) {
      const resolved = await getWeeklyRatings(season, pinned.id);
      return resolved;
    }
  }

  // Default, "current", and unmapped params: the active model state. The
  // served label is derived from the served rows, so the two agree by
  // construction in every projection-before-selection and rollback state.
  // No newest-generation label may be paired with selected-source rows here.
  const ratings = await getCurrentRatings(season);
  const periodMeta = defaultPeriodForRows(ratings);
  return { ratings, period: periodMeta.id, periodMeta };
});

export const getTeamHistory = cache(async (season: number, team: string): Promise<Rating[]> => {
  const sourceSha = await getSelectedRatingSource(season);
  if (!sourceSha) return [];
  const rows = await db.select({
    team: schema.v5RatingSnapshots.team,
    week: schema.v5RatingSnapshots.week,
    cutoffUtc: schema.v5RatingSnapshots.cutoffUtc,
    offenseRating: schema.v5RatingSnapshots.offenseRating,
    offenseVariance: schema.v5RatingSnapshots.offenseVariance,
    defenseRating: schema.v5RatingSnapshots.defenseRating,
    defenseVariance: schema.v5RatingSnapshots.defenseVariance,
    overallRating: schema.v5RatingSnapshots.overallRating,
    overallVariance: schema.v5RatingSnapshots.overallVariance,
    fallbackReason: schema.v5RatingSnapshots.fallbackReason,
  }).from(schema.v5RatingSnapshots)
    .where(and(
      eq(schema.v5RatingSnapshots.season, season),
      eq(schema.v5RatingSnapshots.sourceManifestSha256, sourceSha),
      eq(schema.v5RatingSnapshots.team, team),
      eq(schema.v5RatingSnapshots.snapshotClass, "pregame"),
    ))
    .orderBy(asc(schema.v5RatingSnapshots.cutoffUtc));
  return rows;
});

export const getTeamGames = cache(async (season: number, team: string) => {
  return db.select({
    week: schema.games.week,
    startDate: schema.games.startDate,
    homeTeam: schema.games.homeTeam,
    awayTeam: schema.games.awayTeam,
    predictedMargin: schema.predictions.predictedSpread,
    predictedTotal: schema.predictions.predictedTotal,
    homePoints: schema.gameResults.homePoints,
    awayPoints: schema.gameResults.awayPoints,
    evidenceClass: schema.predictionRuns.evidenceClass,
  }).from(schema.games)
    .leftJoin(schema.siteWeekSelections, and(
      eq(schema.siteWeekSelections.season, schema.games.season),
      eq(schema.siteWeekSelections.week, schema.games.week),
    ))
    .leftJoin(schema.predictionRuns, and(
      eq(schema.siteWeekSelections.runId, schema.predictionRuns.runId),
      inArray(schema.predictionRuns.evidenceClass, ["pending", "replay", "live"]),
      sql`${schema.predictionRuns.modelId} LIKE 'v5-%'`,
    ))
    .leftJoin(schema.predictions, and(
      eq(schema.predictionRuns.runId, schema.predictions.runId),
      eq(schema.predictions.gameId, schema.games.gameId),
    ))
    .leftJoin(schema.gameResults, eq(schema.games.gameId, schema.gameResults.gameId))
    .where(and(
      eq(schema.games.season, season),
      or(eq(schema.games.homeTeam, team), eq(schema.games.awayTeam, team)),
    ))
    .orderBy(asc(schema.games.startDate));
});

type PerformanceRow = {
  evidenceClass: "replay" | "live";
  predictedMargin: number | null;
  predictedTotal: number | null;
  marginStdDev: number | null;
  totalStdDev: number | null;
  homePoints: number | null;
  awayPoints: number | null;
  spreadResult: "win" | "loss" | "push" | null;
  totalResult: "win" | "loss" | "push" | null;
};

export type Performance = {
  classification: "replay" | "live" | "all";
  games: number;
  evaluated: number;
  marginMae: number | null;
  totalMae: number | null;
  marginCoverage95: number | null;
  totalCoverage95: number | null;
  spread: { win: number; loss: number; push: number };
  total: { win: number; loss: number; push: number };
};

function summarize(rows: PerformanceRow[], classification: Performance["classification"]): Performance {
  let marginError = 0;
  let totalError = 0;
  let marginN = 0;
  let totalN = 0;
  let marginInside = 0;
  let totalInside = 0;
  let marginIntervals = 0;
  let totalIntervals = 0;
  const spread = { win: 0, loss: 0, push: 0 };
  const total = { win: 0, loss: 0, push: 0 };
  for (const row of rows) {
    if (row.homePoints !== null && row.awayPoints !== null) {
      const actualMargin = row.homePoints - row.awayPoints;
      const actualTotal = row.homePoints + row.awayPoints;
      if (row.predictedMargin !== null) {
        const error = Math.abs(row.predictedMargin - actualMargin);
        marginError += error;
        marginN += 1;
        if (row.marginStdDev !== null) {
          marginIntervals += 1;
          if (error <= 1.959963984540054 * row.marginStdDev) marginInside += 1;
        }
      }
      if (row.predictedTotal !== null) {
        const error = Math.abs(row.predictedTotal - actualTotal);
        totalError += error;
        totalN += 1;
        if (row.totalStdDev !== null) {
          totalIntervals += 1;
          if (error <= 1.959963984540054 * row.totalStdDev) totalInside += 1;
        }
      }
    }
    if (row.spreadResult) spread[row.spreadResult] += 1;
    if (row.totalResult) total[row.totalResult] += 1;
  }
  return {
    classification,
    games: rows.filter((row) => row.homePoints !== null && row.awayPoints !== null).length,
    evaluated: marginN,
    marginMae: marginN ? marginError / marginN : null,
    totalMae: totalN ? totalError / totalN : null,
    marginCoverage95: marginIntervals ? marginInside / marginIntervals : null,
    totalCoverage95: totalIntervals ? totalInside / totalIntervals : null,
    spread, total,
  };
}

export const getV5Performance = cache(async (
  season: number,
  beforeWeek?: number,
): Promise<Performance[]> => {
  const rows = await db.select({
    evidenceClass: schema.predictionRuns.evidenceClass,
    predictedMargin: schema.predictions.predictedSpread,
    predictedTotal: schema.predictions.predictedTotal,
    marginStdDev: schema.predictions.predictedSpreadStdDev,
    totalStdDev: schema.predictions.predictedTotalStdDev,
    homePoints: schema.gameResults.homePoints,
    awayPoints: schema.gameResults.awayPoints,
    spreadResult: sql<"win" | "loss" | "push" | null>`(
      SELECT result FROM prediction_grades pg WHERE pg.run_id = ${schema.predictions.runId}
        AND pg.game_id = ${schema.predictions.gameId} AND pg.target = 'spread' LIMIT 1
    )`,
    totalResult: sql<"win" | "loss" | "push" | null>`(
      SELECT result FROM prediction_grades pg WHERE pg.run_id = ${schema.predictions.runId}
        AND pg.game_id = ${schema.predictions.gameId} AND pg.target = 'total' LIMIT 1
    )`,
  }).from(schema.siteWeekSelections)
    .innerJoin(schema.predictionRuns, eq(schema.siteWeekSelections.runId, schema.predictionRuns.runId))
    .innerJoin(schema.predictions, eq(schema.predictionRuns.runId, schema.predictions.runId))
    .innerJoin(schema.games, eq(schema.predictions.gameId, schema.games.gameId))
    .leftJoin(schema.gameResults, eq(schema.games.gameId, schema.gameResults.gameId))
    .where(and(
      eq(schema.siteWeekSelections.season, season),
      inArray(schema.predictionRuns.evidenceClass, ["replay", "live"]),
      beforeWeek === undefined ? undefined : lt(schema.siteWeekSelections.week, beforeWeek),
    ));
  const typed = rows as PerformanceRow[];
  return [
    summarize(typed, "all"),
    summarize(typed.filter((row) => row.evidenceClass === "replay"), "replay"),
    summarize(typed.filter((row) => row.evidenceClass === "live"), "live"),
  ];
});

export interface BetRecord {
  win: number;
  loss: number;
  push: number;
  units: number;
  roi: number;
  winRate: number;
}

export interface PerformanceSummary {
  classification: "all" | "replay" | "live";
  games: number;
  evaluated: number;
  spread: BetRecord;
  total: BetRecord;
  combined: BetRecord;
  marginMae: number | null;
  totalMae: number | null;
  marginCoverage95: number | null;
  totalCoverage95: number | null;
}

export interface GradedGamePick {
  gameId: number;
  week: number;
  startDate: Date;
  homeTeam: string;
  awayTeam: string;
  homePoints: number | null;
  awayPoints: number | null;
  marketSpread: number | null;
  predictedSpread: number | null;
  spreadLean: "home" | "away" | null;
  spreadResult: "win" | "loss" | "push" | null;
  spreadUnits: number | null;
  spreadEdge: number | null;
  marketTotal: number | null;
  predictedTotal: number | null;
  totalLean: "over" | "under" | null;
  totalResult: "win" | "loss" | "push" | null;
  totalUnits: number | null;
  totalEdge: number | null;
  highConfidence: boolean;
  evidenceClass: "replay" | "live";
}

export interface PerformanceDetail {
  summary: PerformanceSummary;
  byWeek: Record<number, PerformanceSummary>;
  gradedGames: GradedGamePick[];
  weeks: number[];
}

function computeBetRecord(wins: number, losses: number, pushes: number, units: number): BetRecord {
  const decisions = wins + losses;
  const winRate = decisions > 0 ? (wins / decisions) * 100 : 0;
  const risked = wins + losses + pushes;
  const roi = risked > 0 ? (units / risked) * 100 : 0;
  return {
    win: wins,
    loss: losses,
    push: pushes,
    units: Math.round(units * 100) / 100,
    roi: Math.round(roi * 10) / 10,
    winRate: Math.round(winRate * 10) / 10,
  };
}

type DetailRow = {
  evidenceClass: "replay" | "live";
  week: number;
  gameId: number;
  startDate: Date;
  homeTeam: string;
  awayTeam: string;
  homePoints: number | null;
  awayPoints: number | null;
  marketSpread: number | null;
  marketTotal: number | null;
  predictedSpread: number | null;
  predictedTotal: number | null;
  predictedSpreadStdDev: number | null;
  predictedTotalStdDev: number | null;
  spreadLean: "home" | "away" | null;
  totalLean: "over" | "under" | null;
  edgeSpread: number | null;
  edgeTotal: number | null;
  highConfidence: boolean;
  spreadResult: "win" | "loss" | "push" | null;
  spreadUnits: string | null;
  totalResult: "win" | "loss" | "push" | null;
  totalUnits: string | null;
};

function summarizeDetail(
  rows: DetailRow[],
  classification: PerformanceSummary["classification"],
): PerformanceSummary {
  let marginError = 0;
  let totalError = 0;
  let marginN = 0;
  let totalN = 0;
  let marginInside = 0;
  let totalInside = 0;
  let marginIntervals = 0;
  let totalIntervals = 0;

  let spreadWins = 0, spreadLosses = 0, spreadPushes = 0, spreadUnits = 0;
  let totalWins = 0, totalLosses = 0, totalPushes = 0, totalUnits = 0;

  for (const row of rows) {
    if (row.homePoints !== null && row.awayPoints !== null) {
      const actualMargin = row.homePoints - row.awayPoints;
      const actualTotal = row.homePoints + row.awayPoints;
      if (row.predictedSpread !== null) {
        const error = Math.abs(row.predictedSpread - actualMargin);
        marginError += error;
        marginN += 1;
        if (row.predictedSpreadStdDev !== null) {
          marginIntervals += 1;
          if (error <= 1.959963984540054 * row.predictedSpreadStdDev) marginInside += 1;
        }
      }
      if (row.predictedTotal !== null) {
        const error = Math.abs(row.predictedTotal - actualTotal);
        totalError += error;
        totalN += 1;
        if (row.predictedTotalStdDev !== null) {
          totalIntervals += 1;
          if (error <= 1.959963984540054 * row.predictedTotalStdDev) totalInside += 1;
        }
      }
    }

    if (row.spreadResult) {
      if (row.spreadResult === "win") spreadWins++;
      else if (row.spreadResult === "loss") spreadLosses++;
      else if (row.spreadResult === "push") spreadPushes++;

      const u = row.spreadUnits !== null
        ? parseFloat(row.spreadUnits)
        : (row.spreadResult === "win" ? 0.9091 : row.spreadResult === "loss" ? -1.0 : 0.0);
      spreadUnits += isNaN(u) ? 0 : u;
    }

    if (row.totalResult) {
      if (row.totalResult === "win") totalWins++;
      else if (row.totalResult === "loss") totalLosses++;
      else if (row.totalResult === "push") totalPushes++;

      const u = row.totalUnits !== null
        ? parseFloat(row.totalUnits)
        : (row.totalResult === "win" ? 0.9091 : row.totalResult === "loss" ? -1.0 : 0.0);
      totalUnits += isNaN(u) ? 0 : u;
    }
  }

  const spread = computeBetRecord(spreadWins, spreadLosses, spreadPushes, spreadUnits);
  const total = computeBetRecord(totalWins, totalLosses, totalPushes, totalUnits);
  const combined = computeBetRecord(
    spreadWins + totalWins,
    spreadLosses + totalLosses,
    spreadPushes + totalPushes,
    spreadUnits + totalUnits,
  );

  return {
    classification,
    games: rows.filter((r) => r.homePoints !== null && r.awayPoints !== null).length,
    evaluated: marginN,
    marginMae: marginN ? Math.round((marginError / marginN) * 100) / 100 : null,
    totalMae: totalN ? Math.round((totalError / totalN) * 100) / 100 : null,
    marginCoverage95: marginIntervals ? Math.round((marginInside / marginIntervals) * 1000) / 10 : null,
    totalCoverage95: totalIntervals ? Math.round((totalInside / totalIntervals) * 1000) / 10 : null,
    spread,
    total,
    combined,
  };
}

export const getV5PerformanceDetail = cache(async (
  season: number,
): Promise<PerformanceDetail> => {
  const rows = await db.select({
    evidenceClass: schema.predictionRuns.evidenceClass,
    week: schema.siteWeekSelections.week,
    gameId: schema.games.gameId,
    startDate: schema.games.startDate,
    homeTeam: schema.games.homeTeam,
    awayTeam: schema.games.awayTeam,
    homePoints: schema.gameResults.homePoints,
    awayPoints: schema.gameResults.awayPoints,
    marketSpread: schema.predictions.homeTeamSpreadLine,
    marketTotal: schema.predictions.totalLine,
    predictedSpread: schema.predictions.predictedSpread,
    predictedTotal: schema.predictions.predictedTotal,
    predictedSpreadStdDev: schema.predictions.predictedSpreadStdDev,
    predictedTotalStdDev: schema.predictions.predictedTotalStdDev,
    spreadLean: schema.predictions.spreadLean,
    totalLean: schema.predictions.totalLean,
    edgeSpread: schema.predictions.edgeSpread,
    edgeTotal: schema.predictions.edgeTotal,
    highConfidence: schema.predictions.highConfidence,
    spreadResult: sql<"win" | "loss" | "push" | null>`(
      SELECT result FROM prediction_grades pg WHERE pg.run_id = ${schema.predictions.runId}
        AND pg.game_id = ${schema.predictions.gameId} AND pg.target = 'spread' LIMIT 1
    )`,
    spreadUnits: sql<string | null>`(
      SELECT profit_units FROM prediction_grades pg WHERE pg.run_id = ${schema.predictions.runId}
        AND pg.game_id = ${schema.predictions.gameId} AND pg.target = 'spread' LIMIT 1
    )`,
    totalResult: sql<"win" | "loss" | "push" | null>`(
      SELECT result FROM prediction_grades pg WHERE pg.run_id = ${schema.predictions.runId}
        AND pg.game_id = ${schema.predictions.gameId} AND pg.target = 'total' LIMIT 1
    )`,
    totalUnits: sql<string | null>`(
      SELECT profit_units FROM prediction_grades pg WHERE pg.run_id = ${schema.predictions.runId}
        AND pg.game_id = ${schema.predictions.gameId} AND pg.target = 'total' LIMIT 1
    )`,
  }).from(schema.siteWeekSelections)
    .innerJoin(schema.predictionRuns, eq(schema.siteWeekSelections.runId, schema.predictionRuns.runId))
    .innerJoin(schema.predictions, eq(schema.predictionRuns.runId, schema.predictions.runId))
    .innerJoin(schema.games, eq(schema.predictions.gameId, schema.games.gameId))
    .leftJoin(schema.gameResults, eq(schema.games.gameId, schema.gameResults.gameId))
    .where(and(
      eq(schema.siteWeekSelections.season, season),
      inArray(schema.predictionRuns.evidenceClass, ["replay", "live"]),
    ))
    .orderBy(desc(schema.siteWeekSelections.week), asc(schema.games.startDate));

  const typed = rows as DetailRow[];
  const summary = summarizeDetail(typed, "all");

  const gradedGames: GradedGamePick[] = typed
    .filter((r) => r.spreadResult !== null || r.totalResult !== null)
    .map((r) => ({
      gameId: r.gameId,
      week: r.week,
      startDate: r.startDate,
      homeTeam: r.homeTeam,
      awayTeam: r.awayTeam,
      homePoints: r.homePoints,
      awayPoints: r.awayPoints,
      marketSpread: r.marketSpread,
      predictedSpread: r.predictedSpread,
      spreadLean: r.spreadLean,
      spreadResult: r.spreadResult,
      spreadUnits: r.spreadUnits !== null ? parseFloat(r.spreadUnits) : null,
      spreadEdge: r.edgeSpread,
      marketTotal: r.marketTotal,
      predictedTotal: r.predictedTotal,
      totalLean: r.totalLean,
      totalResult: r.totalResult,
      totalUnits: r.totalUnits !== null ? parseFloat(r.totalUnits) : null,
      totalEdge: r.edgeTotal,
      highConfidence: r.highConfidence,
      evidenceClass: r.evidenceClass,
    }));

  const weeks = Array.from(new Set(gradedGames.map((r) => r.week))).sort((a, b) => a - b);
  const byWeek: Record<number, PerformanceSummary> = {};
  for (const w of weeks) {
    byWeek[w] = summarizeDetail(typed.filter((r) => r.week === w), "all");
  }

  return {
    summary,
    byWeek,
    gradedGames,
    weeks,
  };
});
