/**
 * Server-side launch boundary for the public site. It deliberately defaults
 * to the smallest 2026 release: Week 0 only. Vercel environment values may
 * expand the release after the next slate has passed preview readiness.
 */
const ALLOWED_SEASONS = [2026];
const DEFAULT_SEASON = 2026;
const DEFAULT_WEEKS = Array.from({ length: 17 }, (_, week) => week);

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

export function isAllowedSeason(season: number): boolean {
  return ALLOWED_SEASONS.includes(season);
}

export const publicationScope = Object.freeze({
  season: parseSeason(process.env.CFB_PUBLICATION_SEASON),
  // Explicit public selections in Neon govern available weeks. A stale
  // deployment's V4 week allowlist cannot hide supported V5 history.
  weeks: DEFAULT_WEEKS,
  mode: parsePublicationMode(process.env.CFB_PUBLICATION_MODE),
  allowedSeasons: ALLOWED_SEASONS,
});

export function isPublishedWeek(season: number, week: number): boolean {
  return season === publicationScope.season && publicationScope.weeks.includes(week);
}
