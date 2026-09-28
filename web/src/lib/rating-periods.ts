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
    id: iso,
    label: known ? `Post-Week ${known.postWeek}` : dateLabel,
    shortLabel: known ? `Week ${known.postWeek}` : dateShort,
    description: known
      ? `Frozen ratings after Week ${known.postWeek} games finalized (${known.games} games, weeks ${known.weeks}) (active model state).`
      : "Frozen team ratings from all evidence available at cutoff (active model state).",
    cutoffUtc,
    ...(known ? { postWeek: known.postWeek } : {}),
  } satisfies PeriodMeta;
}

/**
 * Owning source for a frozen cutoff: the source of the newest `current`-class
 * row at that cutoff. Duplicate generations at one cutoff resolve newest-row
 * wins per team; this helper names the source that won. Pure over caller-
 * supplied rows (ordered newest-first) so the rule is unit-testable.
 */
export function ownerSourceForCutoff(
  rows: { sourceManifestSha256: string | null; createdAt: Date }[]
): string | null {
  return rows.find((r) => r.sourceManifestSha256)?.sourceManifestSha256 ?? null;
}
