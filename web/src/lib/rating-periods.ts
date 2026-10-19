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
  /**
   * Résumé fields from `season_release_team_resume`, joined by exact period and team.
   * Absent or null when the release has no row for the team and period (for example,
   * the current release before the projection is staged, or a table not yet migrated).
   */
  wins?: number | null;
  losses?: number | null;
  completedGames?: number | null;
  scheduledGames?: number | null;
  sosPlayedElite?: number | null;
  sosRemainingElite?: number | null;
  sosFullElite?: number | null;
  sosPlayedAverage?: number | null;
  sosRemainingAverage?: number | null;
  sosFullAverage?: number | null;
  sor?: number | null;
  sorRank?: number | null;
  waa?: number | null;
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
 * Résumé facts for one generation, derived from its `season_release_team_resume` rows by
 * `resumeFactsByPeriod` in `./team-resume.ts`. `postWeek` is the certified post-week the
 * generation was assessed after; `games` is its completed-game count.
 */
export type ResumePeriodFacts = { postWeek: number; games: number };

/** Label fields for a generation with résumé facts. `active` marks the active model state. */
export function resumePeriodFields(
  facts: ResumePeriodFacts,
  active: boolean,
): Pick<PeriodMeta, "label" | "shortLabel" | "description" | "postWeek"> {
  const { postWeek, games } = facts;
  const weeks = postWeek === 0 ? "week 0" : `weeks 0–${postWeek}`;
  return {
    label: `Post-Week ${postWeek}`,
    shortLabel: `Week ${postWeek}`,
    description: `Frozen ratings after Week ${postWeek} games finalized (${games} FBS games, ${weeks})${active ? " (active model state)." : "."}`,
    postWeek,
  };
}

/**
 * Label fields for a generation. Résumé facts give the certified post-week label. Without
 * them (no table, no rows for the release, or a rollback target) the label is the cutoff
 * date, so the page never fails for lack of the projection.
 */
export function periodLabelFields(
  cutoff: Date,
  facts: ResumePeriodFacts | undefined,
  active: boolean,
): Pick<PeriodMeta, "label" | "shortLabel" | "description" | "postWeek"> {
  if (facts) return resumePeriodFields(facts, active);
  return {
    ...formatCutoffLabel(cutoff),
    description: active
      ? "Frozen team ratings from all evidence available at cutoff (active model state)."
      : "Frozen team ratings from all evidence available at cutoff.",
  };
}

/**
 * Default-view period derived from the served rows, not from the newest
 * generation present. The default branch must pair this label with the exact
 * rows it was derived from, so label and data agree by construction in every
 * projection-before-selection and rollback state. Callers must pass
 * single-cutoff rows (`getCurrentRatings` guarantees its source's max
 * cutoff); empty input yields the preseason meta. `resumeFacts` is keyed by
 * period id and may be empty.
 */
export function defaultPeriodForRows(
  ratings: Rating[],
  resumeFacts: ReadonlyMap<string, ResumePeriodFacts>,
): PeriodMeta {
  if (ratings.length === 0) return PRESEASON_META;
  const { sourceManifestSha256, cutoffUtc } = ratings[0];
  const id = sourceManifestSha256 ? sourceQualifiedPeriodId(sourceManifestSha256, cutoffUtc) : cutoffUtc.toISOString();
  return {
    id,
    cutoffUtc,
    ...(sourceManifestSha256 ? { sourceManifestSha256 } : {}),
    ...periodLabelFields(cutoffUtc, resumeFacts.get(id), true),
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

/**
 * The frozen generation a game's pre-game ratings come from: the latest one
 * whose evidence cutoff is at or before kickoff (periods may be in any order).
 * Null when none qualifies (Week 0), where callers use the preseason priors.
 */
export function periodBeforeKickoff(periods: PeriodMeta[], kickoff: Date): PeriodMeta | null {
  let best: PeriodMeta | null = null;
  for (const period of periods) {
    if (!period.cutoffUtc || period.cutoffUtc.getTime() > kickoff.getTime()) continue;
    if (!best || period.cutoffUtc.getTime() > (best.cutoffUtc as Date).getTime()) best = period;
  }
  return best;
}
