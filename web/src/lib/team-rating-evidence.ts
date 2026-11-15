import { getSeasonDb, getSeasonReleaseContext } from "./season-release";
import { ratingComponentsQuery, teamScheduleQuery } from "./matchup-rating-query";
import { buildUnitBreakdown, componentId, type UnitRatingBreakdown } from "./rating-breakdown";
import { nationalRanks } from "./team-analysis";
import type { Rating } from "./rating-periods";

/** The evidence is tied to the exact displayed snapshot, not the latest available week. */
export async function getTeamRatingEvidence(season: number, gameTeam: string, row: Rating, population: Rating[]): Promise<UnitRatingBreakdown[]> {
  const roles = ["offense", "defense"] as const;
  const unavailable = (reason: "missing" | "lookup"): UnitRatingBreakdown[] => roles.map((role) => ({ role, status: "unavailable", reason }));
  if (!row.snapshotId || !row.sourceManifestSha256) return unavailable("missing");
  // Components must be resolved through an active immutable release, never the legacy fallback.
  if (!await getSeasonReleaseContext(season)) return unavailable("missing");
  try {
    const db = await getSeasonDb(season);
    const [components, schedule] = await Promise.all([
      ratingComponentsQuery(db, season, row.sourceManifestSha256, roles.map((role) => componentId(row.snapshotId!, role))),
      teamScheduleQuery(db, season, [gameTeam]),
    ]);
    return roles.map((role) => buildUnitBreakdown({ role, team: gameTeam,
      rendered: { snapshotId: row.snapshotId, sourceManifestSha256: row.sourceManifestSha256, ratingTeam: row.team,
        rating: role === "offense" ? row.offenseRating : row.defenseRating, rank: nationalRanks(population, role).get(row.team) ?? null },
      components: new Map(components.map((item) => [item.componentId, item])), schedule: new Map(schedule.map((item) => [item.gameId, item])),
    }));
  } catch (error) {
    console.error("Team rating evidence query failed", error);
    return unavailable("lookup");
  }
}
