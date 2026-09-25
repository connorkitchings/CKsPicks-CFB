/**
 * Server-side launch boundary for the public site. The public week range is
 * owned by this repository (PUBLISHED_WEEKS below), not by a deployment
 * variable: there is no weekly Vercel edit. Within that range, only weeks
 * with an explicit Neon public selection render; unpublished weeks stay
 * hidden until their run is published and selected through the ops flow.
 */
const ALLOWED_SEASONS = [2026];
const DEFAULT_SEASON = 2026;
const PUBLISHED_WEEKS = Array.from({ length: 17 }, (_, week) => week);

export type PublicationMode = "market" | "predictions";

/** Public display names. Manifest and database identities are unchanged. */
const DISPLAY_SYSTEM_NAMES: Record<string, string> = {
  "Trench Warfare V5": "Blitzkrieg",
};

/** Map an internal model system name to its public display name. */
export function displaySystemName(systemName: string | null): string | null {
  if (systemName === null) return null;
  return DISPLAY_SYSTEM_NAMES[systemName] ?? systemName;
}

/** Lean/edge twins of the pipeline _derive_lean rules, for replay display. */
export function deriveSpreadView(
  predictedSpread: number | null,
  homeLine: number | null,
): { lean: "home" | "away" | null; edge: number | null } {
  if (predictedSpread === null || homeLine === null) return { lean: null, edge: null };
  return {
    lean: predictedSpread > -homeLine ? "home" : "away",
    edge: Math.abs(predictedSpread + homeLine),
  };
}

export function deriveTotalView(
  predictedTotal: number | null,
  totalLine: number | null,
): { lean: "over" | "under" | null; edge: number | null } {
  if (predictedTotal === null || totalLine === null) return { lean: null, edge: null };
  return {
    lean: predictedTotal > totalLine ? "over" : "under",
    edge: Math.abs(predictedTotal - totalLine),
  };
}

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
  // Explicit public selections in Neon govern available weeks. The retired
  // CFB_PUBLICATION_WEEKS variable is ignored; edit PUBLISHED_WEEKS above to
  // change the repo-owned range.
  weeks: PUBLISHED_WEEKS,
  mode: parsePublicationMode(process.env.CFB_PUBLICATION_MODE),
  allowedSeasons: ALLOWED_SEASONS,
});

export function isPublishedWeek(season: number, week: number): boolean {
  return season === publicationScope.season && publicationScope.weeks.includes(week);
}
