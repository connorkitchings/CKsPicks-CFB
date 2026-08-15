/**
 * Server-side launch boundary for the public site. It deliberately defaults
 * to the smallest 2026 release: Week 0 only. Vercel environment values may
 * expand the release after the next slate has passed preview readiness.
 */
const DEFAULT_SEASON = 2026;
const DEFAULT_WEEKS = [0];

export type PublicationMode = "market" | "predictions";

/** Fail closed: model output is public only after an exact server-side opt-in. */
export function parsePublicationMode(value: string | undefined): PublicationMode {
  return value === "predictions" ? "predictions" : "market";
}

function parseSeason(value: string | undefined): number {
  const season = Number(value);
  return Number.isInteger(season) && season >= 2021 && season <= 2100
    ? season
    : DEFAULT_SEASON;
}

function parseWeeks(value: string | undefined): number[] {
  if (!value) return DEFAULT_WEEKS;

  const weeks = value
    .split(",")
    .map((item) => Number(item.trim()))
    .filter((week) => Number.isInteger(week) && week >= 0 && week <= 16);

  return weeks.length > 0
    ? [...new Set(weeks)].sort((a, b) => a - b)
    : DEFAULT_WEEKS;
}

export const publicationScope = Object.freeze({
  season: parseSeason(process.env.CFB_PUBLICATION_SEASON),
  weeks: parseWeeks(process.env.CFB_PUBLICATION_WEEKS),
  mode: parsePublicationMode(process.env.CFB_PUBLICATION_MODE),
});

export function isPublishedWeek(season: number, week: number): boolean {
  return season === publicationScope.season && publicationScope.weeks.includes(week);
}
