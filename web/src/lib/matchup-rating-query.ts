import { and, desc, eq, inArray, lte, or } from "drizzle-orm";
import type { getSeasonDb } from "./season-release";
import * as schema from "./schema.ts";

/** The identity travels with the exact rows rendered by getRatingsAsOf. */
export function renderedRatingSource(
  ratings: { team: string; sourceManifestSha256?: string | null }[],
  teams: string[],
): string | null {
  const sources = new Set<string>();
  for (const team of new Set(teams)) {
    const rows = ratings.filter((row) => row.team === team);
    if (rows.length !== 1 || !rows[0].sourceManifestSha256) return null;
    sources.add(rows[0].sourceManifestSha256);
  }
  return sources.size === 1 ? [...sources][0] : null;
}

/** Keep the ordering column in DISTINCT so PostgreSQL can order provenance. */
export function matchupRatingQuery(
  db: Awaited<ReturnType<typeof getSeasonDb>>,
  season: number,
  kickoff: Date,
  teams: string[],
  sourceManifestSha256: string,
) {
  return db.selectDistinct({
    team: schema.v5RatingSnapshots.team,
    sourceManifestSha256: schema.v5RatingSnapshots.sourceManifestSha256,
    cutoffUtc: schema.v5RatingSnapshots.cutoffUtc,
  }).from(schema.v5RatingSnapshots).where(and(
    eq(schema.v5RatingSnapshots.season, season),
    eq(schema.v5RatingSnapshots.snapshotClass, "current"),
    eq(schema.v5RatingSnapshots.sourceManifestSha256, sourceManifestSha256),
    lte(schema.v5RatingSnapshots.cutoffUtc, kickoff),
    inArray(schema.v5RatingSnapshots.team, teams),
  )).orderBy(desc(schema.v5RatingSnapshots.cutoffUtc));
}

/**
 * Component rows are keyed by `component_id`, so no cutoff or week predicate is needed: the
 * ids come from the rendered snapshot ids. The source is pinned to the rendered rating source.
 */
export function ratingComponentsQuery(
  db: Awaited<ReturnType<typeof getSeasonDb>>,
  season: number,
  sourceManifestSha256: string,
  componentIds: string[],
) {
  const c = schema.teamRatingComponents;
  return db.select({
    componentId: c.componentId,
    v5SnapshotId: c.v5SnapshotId,
    sourceManifestSha256: c.sourceManifestSha256,
    ratingTeam: c.ratingTeam,
    unitRole: c.unitRole,
    ratingMean: c.ratingMean,
    priorWeight: c.priorWeight,
    priorContribution: c.priorContribution,
    usableExposure: c.usableExposure,
    completedGames: c.completedGames,
    evidence: c.evidence,
    excludedObservations: c.excludedObservations,
  }).from(c).where(and(
    eq(c.season, season),
    eq(c.sourceManifestSha256, sourceManifestSha256),
    inArray(c.componentId, componentIds),
  ));
}

/** Every scheduled game of the given teams, for opponent names. */
export function teamScheduleQuery(
  db: Awaited<ReturnType<typeof getSeasonDb>>,
  season: number,
  teams: string[],
) {
  const g = schema.games;
  return db.select({ gameId: g.gameId, week: g.week, homeTeam: g.homeTeam, awayTeam: g.awayTeam })
    .from(g)
    .where(and(eq(g.season, season), or(inArray(g.homeTeam, teams), inArray(g.awayTeam, teams))));
}
