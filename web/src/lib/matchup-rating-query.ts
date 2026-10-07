import { and, desc, eq, inArray, lte } from "drizzle-orm";
import type { NeonHttpDatabase } from "drizzle-orm/neon-http";
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
  db: NeonHttpDatabase<typeof schema>,
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
