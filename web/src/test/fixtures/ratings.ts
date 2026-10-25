import type { RosterRow } from "@/lib/charts";
import type { PeriodMeta, Rating } from "@/lib/rating-periods";

export const ratingsRosterFixture: RosterRow[] = [
  { team: "Texas", conference: "SEC" },
  { team: "Ohio State", conference: "Big Ten" },
  { team: "Appalachian State", conference: "Sun Belt" },
  { team: "Southern Mississippi", conference: "Sun Belt" },
];

const earlierCutoff = new Date("2026-09-22T14:58:00.000Z");
const currentCutoff = new Date("2026-09-27T14:15:00.000Z");
const source = "a".repeat(64);
const earlierId = `${source}@${earlierCutoff.toISOString()}`;
const currentId = `${source}@${currentCutoff.toISOString()}`;

/**
 * Requesting this period id serves the current ratings with no résumé rows: the state of a
 * release without `season_release_team_resume` (no table, or no rows for the release).
 */
export const NO_RESUME_PERIOD = "no-resume";

/** Latest first, as `getRatingPeriods` lists them in production. */
export const ratingPeriodsFixture: PeriodMeta[] = [
  { id: currentId, label: "Post-Week 4", shortLabel: "Week 4", description: "Frozen ratings after Week 4 games finalized (active model state).", cutoffUtc: currentCutoff, sourceManifestSha256: source, postWeek: 4 },
  { id: earlierId, label: "Post-Week 3", shortLabel: "Week 3", description: "Frozen ratings after Week 3 games finalized.", cutoffUtc: earlierCutoff, sourceManifestSha256: source, postWeek: 3 },
  { id: "preseason", label: "Preseason", shortLabel: "Preseason", description: "Preseason baseline priors before 2026 kickoff." },
];

const teams = [
  { team: "Texas", offenseRating: 3.4, defenseRating: 2.1 },
  { team: "Ohio State", offenseRating: 4.8, defenseRating: 0.2 },
  { team: "Appalachian State", offenseRating: 1.2, defenseRating: 3.6 },
  { team: "Southern Mississippi", offenseRating: -0.5, defenseRating: 1.5 },
];

type ResumeFields = Pick<Rating,
  | "wins" | "losses" | "completedGames" | "scheduledGames"
  | "sosPlayedElite" | "sosRemainingElite" | "sosFullElite"
  | "sosPlayedAverage" | "sosRemainingAverage" | "sosFullAverage"
  | "sor" | "sorRank" | "waa">;

const NO_RESUME: ResumeFields = {
  wins: null, losses: null, completedGames: null, scheduledGames: null,
  sosPlayedElite: null, sosRemainingElite: null, sosFullElite: null,
  sosPlayedAverage: null, sosRemainingAverage: null, sosFullAverage: null,
  sor: null, sorRank: null, waa: null,
};

// Hand-written, internally consistent numbers. Every team has 12 scheduled games, so Full is the
// games-weighted mean of Played and Remaining. SOS is the mean of (1 - reference win probability) x 100,
// and an elite reference wins more often, so its SOS is lower than Average. SOR and WAA need at least
// 3 completed FBS games: Southern Mississippi has 2 and gets null for both.
const resumeByPeriod: Record<string, Record<string, ResumeFields>> = {
  [earlierId]: {
    "Texas": {
      wins: 3, losses: 0, completedGames: 3, scheduledGames: 12,
      sosPlayedElite: 40.0, sosRemainingElite: 47.9, sosFullElite: 45.9,
      sosPlayedAverage: 51.4, sosRemainingAverage: 58.4, sosFullAverage: 56.7,
      sor: 74.0, sorRank: 2, waa: 1.2,
    },
    "Ohio State": {
      wins: 2, losses: 1, completedGames: 3, scheduledGames: 12,
      sosPlayedElite: 35.2, sosRemainingElite: 44.2, sosFullElite: 42.0,
      sosPlayedAverage: 47.5, sosRemainingAverage: 55.7, sosFullAverage: 53.7,
      sor: 80.5, sorRank: 1, waa: -0.3,
    },
    "Appalachian State": {
      wins: 2, losses: 1, completedGames: 3, scheduledGames: 12,
      sosPlayedElite: 50.2, sosRemainingElite: 55.1, sosFullElite: 53.9,
      sosPlayedAverage: 60.1, sosRemainingAverage: 64.9, sosFullAverage: 63.7,
      sor: 40.2, sorRank: 3, waa: 0.6,
    },
    "Southern Mississippi": {
      wins: 1, losses: 1, completedGames: 2, scheduledGames: 12,
      sosPlayedElite: 55.0, sosRemainingElite: 58.6, sosFullElite: 58.0,
      sosPlayedAverage: 63.0, sosRemainingAverage: 66.0, sosFullAverage: 65.5,
      sor: null, sorRank: null, waa: null,
    },
  },
  [currentId]: {
    "Texas": {
      wins: 4, losses: 0, completedGames: 4, scheduledGames: 12,
      sosPlayedElite: 41.3, sosRemainingElite: 47.9, sosFullElite: 45.7,
      sosPlayedAverage: 52.6, sosRemainingAverage: 58.4, sosFullAverage: 56.5,
      sor: 81.2, sorRank: 2, waa: 1.6,
    },
    "Ohio State": {
      wins: 3, losses: 1, completedGames: 4, scheduledGames: 12,
      sosPlayedElite: 36.8, sosRemainingElite: 44.2, sosFullElite: 41.7,
      sosPlayedAverage: 49.1, sosRemainingAverage: 55.7, sosFullAverage: 53.5,
      sor: 93.7, sorRank: 1, waa: 2.1,
    },
    "Appalachian State": {
      wins: 2, losses: 2, completedGames: 4, scheduledGames: 12,
      sosPlayedElite: 52.4, sosRemainingElite: 55.1, sosFullElite: 54.2,
      sosPlayedAverage: 61.7, sosRemainingAverage: 64.9, sosFullAverage: 63.8,
      sor: 47.9, sorRank: 3, waa: -0.4,
    },
    "Southern Mississippi": {
      wins: 1, losses: 1, completedGames: 2, scheduledGames: 12,
      sosPlayedElite: 55.0, sosRemainingElite: 58.6, sosFullElite: 58.0,
      sosPlayedAverage: 63.0, sosRemainingAverage: 66.0, sosFullAverage: 65.5,
      sor: null, sorRank: null, waa: null,
    },
  },
};

/** Multiple category leaders and frozen periods exercise mobile comparison behavior. */
export function ratingsFixture(requestedPeriod: string) {
  const withResume = requestedPeriod !== NO_RESUME_PERIOD;
  const periodMeta = ratingPeriodsFixture.find((entry) => entry.id === requestedPeriod)
    ?? ratingPeriodsFixture[0];
  const adjustment = periodMeta.id === "preseason" ? -0.4 : periodMeta.postWeek === 3 ? -0.2 : 0;
  const resumeRows = withResume ? resumeByPeriod[periodMeta.id] ?? {} : {};
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
      ...(resumeRows[team.team] ?? NO_RESUME),
    };
  });
  return { ratings, period: periodMeta.id, periodMeta, timeline: ratingPeriodsFixture };
}
