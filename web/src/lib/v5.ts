import { and, asc, desc, eq, inArray, lt, or, sql } from "drizzle-orm";
import { cache } from "react";
import { db, schema } from "./db";

export type Rating = {
  team: string;
  week: number;
  cutoffUtc: Date;
  offenseRating: number;
  offenseVariance: number;
  defenseRating: number;
  defenseVariance: number;
  overallRating: number;
  overallVariance: number;
  fallbackReason: string | null;
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

/** A ratings period id: "preseason" or an exact generation cutoff ISO string. */
export type RatingPeriod = string;

export interface PeriodMeta {
  id: RatingPeriod;
  label: string;
  shortLabel: string;
  description: string;
  /** Set for frozen generations; absent for the preseason entry. */
  cutoffUtc?: Date;
  /** Set when the generation is the certified post-week assessment. */
  postWeek?: number;
}

const PRESEASON_META: PeriodMeta = {
  id: "preseason",
  label: "Preseason",
  shortLabel: "Preseason",
  description: "Preseason baseline priors before 2026 kickoff.",
};

function formatCutoffLabel(cutoff: Date): { label: string; shortLabel: string } {
  const label = `As of ${cutoff.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" })}`;
  const shortLabel = cutoff.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  return { label, shortLabel };
}

/**
 * Certified post-week assessments, keyed by exact generation cutoff ISO.
 * A generation earns a week label only after its full replay→verify→project
 * chain completes; unknown future cutoffs keep their "As of" date label
 * until then. Week coverage below is the verified completed-game count.
 */
export const WEEK_GENERATIONS: Record<string, { postWeek: number; games: number; weeks: string }> = {
  "2026-09-03T04:00:00.000Z": { postWeek: 0, games: 8, weeks: "0" },
  "2026-09-08T15:35:00.000Z": { postWeek: 1, games: 51, weeks: "0–1" },
  "2026-09-13T18:18:22.000Z": { postWeek: 2, games: 100, weeks: "0–2" },
  "2026-09-22T14:58:00.000Z": { postWeek: 3, games: 157, weeks: "0–3" },
  "2026-09-27T14:15:00.000Z": { postWeek: 4, games: 215, weeks: "0–4" },
};

/**
 * Ratings timeline derived from the data, not from hardcoded weeks. Every
 * frozen `current`-class generation is one entry addressable by its exact
 * evidence cutoff; the newest entry is the active model state. New weekly
 * projections appear here with no code change, and past generations can
 * never drift: each one is served from its own frozen rows.
 */
export const getRatingPeriods = cache(async (season: number): Promise<PeriodMeta[]> => {
  const rows = await db.selectDistinct({ cutoffUtc: schema.v5RatingSnapshots.cutoffUtc })
    .from(schema.v5RatingSnapshots)
    .where(and(
      eq(schema.v5RatingSnapshots.season, season),
      eq(schema.v5RatingSnapshots.snapshotClass, "current"),
    ))
    .orderBy(desc(schema.v5RatingSnapshots.cutoffUtc));
  const periods = rows.map(({ cutoffUtc }, index) => {
    const iso = cutoffUtc.toISOString();
    const known = WEEK_GENERATIONS[iso];
    const { label: dateLabel, shortLabel: dateShort } = formatCutoffLabel(cutoffUtc);
    const active = index === 0;
    return {
      id: iso,
      label: known ? `Post-Week ${known.postWeek}` : dateLabel,
      shortLabel: known ? `Week ${known.postWeek}` : dateShort,
      description: known
        ? `Frozen ratings after Week ${known.postWeek} games finalized (${known.games} games, weeks ${known.weeks})${active ? " (active model state)." : "."}`
        : active
          ? "Frozen team ratings from all evidence available at cutoff (active model state)."
          : "Frozen team ratings from all evidence available at cutoff.",
      cutoffUtc,
      ...(known ? { postWeek: known.postWeek } : {}),
    } satisfies PeriodMeta;
  });
  return [...periods, PRESEASON_META];
});

const RATING_SELECT = {
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
};

async function getPreseasonPriors(season: number): Promise<Rating[]> {
  const sourceSha = await getSelectedRatingSource(season);
  if (!sourceSha) return [];
  return db.select(RATING_SELECT).from(schema.v5RatingSnapshots)
    .where(and(
      eq(schema.v5RatingSnapshots.season, season),
      eq(schema.v5RatingSnapshots.sourceManifestSha256, sourceSha),
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

  // Exact generation cutoff: serve that generation's frozen rows. No source
  // pin: a frozen assessment is self-identifying by cutoff and must not move
  // when later generations are projected.
  const frozen = generations.find((p) => p.id === targetPeriod);
  if (frozen?.cutoffUtc) {
    const rows = await db.select(RATING_SELECT).from(schema.v5RatingSnapshots)
      .where(and(
        eq(schema.v5RatingSnapshots.season, season),
        eq(schema.v5RatingSnapshots.snapshotClass, "current"),
        eq(schema.v5RatingSnapshots.cutoffUtc, frozen.cutoffUtc),
      ))
      .orderBy(desc(schema.v5RatingSnapshots.createdAt));
    const byTeam = new Map<string, Rating>();
    for (const row of rows) {
      if (!byTeam.has(row.team)) {
        byTeam.set(row.team, row);
      }
    }
    // Early generations cover only teams that had played by the cutoff
    // (post-Week 0: 16 teams). Backfill the rest from preseason priors so
    // every tab lists all 138 FBS teams; prior rows carry their own
    // fallback lineage.
    for (const prior of await getPreseasonPriors(season)) {
      if (!byTeam.has(prior.team)) {
        byTeam.set(prior.team, prior);
      }
    }
    const ratings = [...byTeam.values()].sort((a, b) => b.overallRating - a.overallRating);
    return { ratings, period: frozen.id, periodMeta: frozen };
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

  // Default, "current", and unmapped params: the newest generation, i.e. the
  // active model state. The served label always matches the data.
  const latest = generations[0];
  if (!latest) return { ratings: [], period: "preseason", periodMeta: PRESEASON_META };
  const ratings = await getCurrentRatings(season);
  return { ratings, period: latest.id, periodMeta: latest };
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
    games: rows.length,
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
