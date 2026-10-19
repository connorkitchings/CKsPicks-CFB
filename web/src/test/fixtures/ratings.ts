import type { PeriodMeta, Rating } from "@/lib/rating-periods";

const earlierCutoff = new Date("2026-09-22T14:58:00.000Z");
const currentCutoff = new Date("2026-09-27T14:15:00.000Z");
const source = "a".repeat(64);

export const ratingPeriodsFixture: PeriodMeta[] = [
  { id: "preseason", label: "Preseason", shortLabel: "Preseason", description: "Preseason baseline priors before 2026 kickoff." },
  { id: `${source}@${earlierCutoff.toISOString()}`, label: "Post-Week 3", shortLabel: "Week 3", description: "Frozen ratings after Week 3 games finalized.", cutoffUtc: earlierCutoff, sourceManifestSha256: source, postWeek: 3 },
  { id: `${source}@${currentCutoff.toISOString()}`, label: "Post-Week 4", shortLabel: "Week 4", description: "Frozen ratings after Week 4 games finalized (active model state).", cutoffUtc: currentCutoff, sourceManifestSha256: source, postWeek: 4 },
];

const teams = [
  { team: "Texas", offenseRating: 3.4, defenseRating: 2.1 },
  { team: "Ohio State", offenseRating: 4.8, defenseRating: 0.2 },
  { team: "Appalachian State", offenseRating: 1.2, defenseRating: 3.6 },
  { team: "Southern Mississippi", offenseRating: -0.5, defenseRating: 1.5 },
];

/** Multiple category leaders and frozen periods exercise mobile comparison behavior. */
export function ratingsFixture(requestedPeriod: string) {
  const periodMeta = ratingPeriodsFixture.find((entry) => entry.id === requestedPeriod)
    ?? ratingPeriodsFixture[2];
  const adjustment = periodMeta.id === "preseason" ? -0.4 : periodMeta.postWeek === 3 ? -0.2 : 0;
  const ratings: Rating[] = teams.map((team) => {
    const offenseRating = team.offenseRating + adjustment;
    const defenseRating = team.defenseRating;
    return {
      team: team.team,
      week: periodMeta.postWeek ?? 0,
      cutoffUtc: periodMeta.cutoffUtc ?? new Date("2026-08-22T00:00:00.000Z"),
      sourceManifestSha256: source,
      offenseRating,
      defenseRating,
      overallRating: offenseRating + defenseRating,
      offenseVariance: 1.44,
      defenseVariance: 1.21,
      overallVariance: 2.65,
      fallbackReason: null,
    };
  });
  return { ratings, period: periodMeta.id, periodMeta, timeline: ratingPeriodsFixture };
}
