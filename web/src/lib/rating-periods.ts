/**
 * Pure ratings-period helpers shared by the serving layer and its tests.
 *
 * This module is intentionally dependency-free (no database, no React): the
 * serving queries in `./v5` import from here, and behavioral tests import
 * from here without pulling the drizzle/Neon client chain, which plain
 * `node:test` cannot resolve.
 */

export type Rating = {
  team: string;
  sourceManifestSha256?: string;
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

/** A ratings period id: "preseason" or a source-qualified generation cutoff. */
export type RatingPeriod = string;

export interface PeriodMeta {
  id: RatingPeriod;
  label: string;
  shortLabel: string;
  description: string;
  /** Set for frozen generations; absent for the preseason entry. */
  cutoffUtc?: Date;
  sourceManifestSha256?: string;
  /** Set when the generation is the certified post-week assessment. */
  postWeek?: number;
}

export const PRESEASON_META: PeriodMeta = {
  id: "preseason",
  label: "Preseason",
  shortLabel: "Preseason",
  description: "Preseason baseline priors before 2026 kickoff.",
};

export function formatCutoffLabel(cutoff: Date): { label: string; shortLabel: string } {
  const label = `As of ${cutoff.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" })}`;
  const shortLabel = cutoff.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  return { label, shortLabel };
}

export function sourceQualifiedPeriodId(sourceSha: string, cutoff: Date): string {
  if (!/^[a-f0-9]{64}$/.test(sourceSha)) throw new Error("Invalid rating source SHA");
  return `${sourceSha}@${cutoff.toISOString()}`;
}

export function parseSourceQualifiedPeriodId(id: string): { sourceSha: string; cutoff: Date } | null {
  const match = id.match(/^([a-f0-9]{64})@(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)$/);
  if (!match) return null;
  const cutoff = new Date(match[2]);
  return Number.isNaN(cutoff.getTime()) ? null : { sourceSha: match[1], cutoff };
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
 * Default-view period derived from the served rows, not from the newest
 * generation present. The default branch must pair this label with the exact
 * rows it was derived from, so label and data agree by construction in every
 * projection-before-selection and rollback state. Callers must pass
 * single-cutoff rows (`getCurrentRatings` guarantees its source's max
 * cutoff); empty input yields the preseason meta.
 */
export function defaultPeriodForRows(ratings: Rating[]): PeriodMeta {
  if (ratings.length === 0) return PRESEASON_META;
  const cutoffUtc = ratings[0].cutoffUtc;
  const iso = cutoffUtc.toISOString();
  const known = WEEK_GENERATIONS[iso];
  const { label: dateLabel, shortLabel: dateShort } = formatCutoffLabel(cutoffUtc);
  return {
    id: ratings[0].sourceManifestSha256
      ? sourceQualifiedPeriodId(ratings[0].sourceManifestSha256, cutoffUtc)
      : iso,
    label: known ? `Post-Week ${known.postWeek}` : dateLabel,
    shortLabel: known ? `Week ${known.postWeek}` : dateShort,
    description: known
      ? `Frozen ratings after Week ${known.postWeek} games finalized (${known.games} games, weeks ${known.weeks}) (active model state).`
      : "Frozen team ratings from all evidence available at cutoff (active model state).",
    cutoffUtc,
    ...(ratings[0].sourceManifestSha256 ? { sourceManifestSha256: ratings[0].sourceManifestSha256 } : {}),
    ...(known ? { postWeek: known.postWeek } : {}),
  } satisfies PeriodMeta;
}

/**
 * Legacy unqualified links resolve to the first source published at a cutoff.
 * Later projections can share that cutoff without changing old deep links.
 */
export function ownerSourceForCutoff(
  rows: { sourceManifestSha256: string | null; createdAt: Date }[]
): string | null {
  return [...rows]
    .filter((r) => r.sourceManifestSha256)
    .sort((a, b) => a.createdAt.getTime() - b.createdAt.getTime()
      || a.sourceManifestSha256!.localeCompare(b.sourceManifestSha256!))[0]?.sourceManifestSha256 ?? null;
}
