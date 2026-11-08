/**
 * Pure builder for the matchup page's "How the ratings are built" section.
 *
 * Dependency-free (no database, no React), like `rating-periods.ts`, so behavioral tests
 * import it directly. Each unit's rendered rating is checked against its stored component
 * row and the row's own arithmetic before any number is shown; a failed check yields an
 * `unavailable` unit (never partial or coerced figures).
 */
export type UnitRole = "offense" | "defense";
export type UnavailableReason = "missing" | "mismatch" | "invalid" | "lookup";

export interface BreakdownGame {
  gameId: number;
  week: number;
  opponent: string | null;
  /** Possessions behind this game's observation. */
  exposure: number;
  rawPpp: number;
  adjustedPpp: number;
  contribution: number;
  /** True when the opponent had no adjustment context, so adjusted equals raw. */
  missingContext: boolean;
}

export interface ExcludedGame {
  gameId: number;
  week: number;
  opponent: string | null;
  reason: string;
}

export type UnitRatingBreakdown =
  | {
      status: "ready";
      role: UnitRole;
      rating: number;
      rank: number | null;
      priorWeight: number;
      priorContribution: number;
      /** Exposure-weighted means over the evidence ledger; null before any game is used. */
      rawPpp: number | null;
      adjustedPpp: number | null;
      possessions: number;
      completedGames: number;
      games: BreakdownGame[];
      excluded: ExcludedGame[];
    }
  | { status: "unavailable"; role: UnitRole; reason: UnavailableReason };

export interface RatingBreakdown {
  awayOffense: UnitRatingBreakdown;
  awayDefense: UnitRatingBreakdown;
  homeOffense: UnitRatingBreakdown;
  homeDefense: UnitRatingBreakdown;
}

/** The `season_release_team_rating_components` columns the breakdown reads. */
export interface ComponentRow {
  componentId: string;
  v5SnapshotId: string | null;
  sourceManifestSha256: string;
  ratingTeam: string;
  unitRole: string;
  ratingMean: number;
  priorWeight: number | null;
  priorContribution: number | null;
  usableExposure: number | null;
  completedGames: number | null;
  evidence: unknown;
  excludedObservations: unknown;
}

export interface ScheduledGame {
  week: number;
  homeTeam: string;
  awayTeam: string;
}

/** What the page rendered for one unit: the rating row it came from and the displayed values. */
export interface RenderedUnit {
  snapshotId?: string;
  sourceManifestSha256?: string;
  /** The rating-table team name (not the game name). */
  ratingTeam: string;
  rating: number;
  rank: number | null;
}

export interface ParsedComponent {
  ratingMean: number;
  priorWeight: number;
  priorContribution: number;
  usableExposure: number;
  completedGames: number;
  evidence: {
    gameId: number;
    week: number;
    exposure: number;
    rawPpp: number;
    adjustedPpp: number;
    contribution: number;
    missingContext: boolean;
  }[];
  excluded: { gameId: number; week: number; reason: string | null }[];
}

const RATING_TOLERANCE = 1e-12;
const IDENTITY_TOLERANCE = 1e-9;

export const componentId = (snapshotId: string, role: UnitRole) => `${snapshotId}:${role}`;

const isNumber = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const isInteger = (value: unknown): value is number => typeof value === "number" && Number.isInteger(value);
const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
/** NaN-safe: true only when both are finite and within `tolerance`. */
const within = (a: number, b: number, tolerance: number) => Math.abs(a - b) <= tolerance;

function jsonArray(value: unknown): unknown[] | null {
  if (typeof value === "string") {
    try {
      value = JSON.parse(value);
    } catch {
      return null;
    }
  }
  return Array.isArray(value) ? value : null;
}

/** Strict parse of one component row. Never coerces; null means the row is not usable. */
export function parseComponent(row: ComponentRow): ParsedComponent | null {
  const { ratingMean, priorWeight, priorContribution, usableExposure, completedGames } = row;
  if (!isNumber(ratingMean) || !isNumber(priorWeight) || priorWeight < 0 || priorWeight > 1) return null;
  if (!isNumber(priorContribution) || !isNumber(usableExposure) || !isInteger(completedGames)) return null;
  const evidenceItems = jsonArray(row.evidence);
  const excludedItems = jsonArray(row.excludedObservations);
  if (!evidenceItems || !excludedItems) return null;

  const evidence: ParsedComponent["evidence"] = [];
  for (const item of evidenceItems) {
    if (!isRecord(item)) return null;
    const reason = item.missing_context_reason;
    if (!isInteger(item.game_id) || !isInteger(item.source_week) || !isNumber(item.exposure)
      || !isNumber(item.raw_ppp) || !isNumber(item.adjusted_ppp) || !isNumber(item.contribution)
      || !(reason === null || typeof reason === "string")) return null;
    evidence.push({
      gameId: item.game_id,
      week: item.source_week,
      exposure: item.exposure,
      rawPpp: item.raw_ppp,
      adjustedPpp: item.adjusted_ppp,
      contribution: item.contribution,
      missingContext: reason !== null,
    });
  }
  const excluded: ParsedComponent["excluded"] = [];
  for (const item of excludedItems) {
    if (!isRecord(item) || !isInteger(item.game_id) || !isInteger(item.week)
      || !(item.reason === null || typeof item.reason === "string")) return null;
    excluded.push({ gameId: item.game_id, week: item.week, reason: item.reason });
  }
  return { ratingMean, priorWeight, priorContribution, usableExposure, completedGames, evidence, excluded };
}

/** The other team in a scheduled game, or null when the game is absent or does not include `team`. */
export function opponentFor(game: Pick<ScheduledGame, "homeTeam" | "awayTeam"> | undefined, team: string): string | null {
  if (!game) return null;
  if (game.homeTeam === team) return game.awayTeam;
  if (game.awayTeam === team) return game.homeTeam;
  return null;
}

const EXCLUDED_REASONS: Record<string, string> = {
  unresolved_scoring_attribution: "scoring could not be attributed to a possession",
};

export const excludedReasonLabel = (code: string | null) =>
  (code !== null && EXCLUDED_REASONS[code]) || "failed a data-quality check";

export const pppText = (value: number) => value.toFixed(2);
export const contributionText = (value: number) => `${value >= 0 ? "+" : ""}${value.toFixed(3)}`;
export const priorPercent = (weight: number) => `${Math.round(weight * 100)}%`;

const SMALL_ADJUSTMENT = 0.05;

/**
 * Plain-language reading of raw versus adjusted points per possession. A higher adjusted
 * value means a tougher offense schedule's defenses (offense) or weaker opposing offenses (defense).
 */
export function adjustmentSentence(role: UnitRole, rawPpp: number, adjustedPpp: number): string {
  const verb = role === "offense" ? "Scores" : "Allows";
  const faced = role === "offense" ? "defenses" : "offenses";
  const lead = `${verb} ${pppText(rawPpp)} points per possession.`;
  const delta = adjustedPpp - rawPpp;
  if (Math.abs(delta) < SMALL_ADJUSTMENT) {
    return `${lead} Opponents were about average ${faced}, so the adjustment is small.`;
  }
  const tougher = role === "offense" ? delta > 0 : delta < 0;
  return `${lead} Against ${tougher ? "tougher" : "weaker"}-than-average ${faced}, the model counts that as ${pppText(adjustedPpp)}.`;
}

/** Rating headline with its position relative to an average team (0). */
export function ratingStanding(rating: number): string {
  if (rating === 0) return "average";
  return rating > 0 ? "above average" : "below average";
}

const unavailable = (role: UnitRole, reason: UnavailableReason): UnitRatingBreakdown =>
  ({ status: "unavailable", role, reason });

/**
 * `components` and `schedule` are null when their lookup failed. Guards run in order:
 * nothing rendered or stored (`missing`), lookup failure (`lookup`), identity differs from
 * what was rendered (`mismatch`), row fails its own arithmetic (`invalid`).
 */
export function buildUnitBreakdown(input: {
  role: UnitRole;
  team: string;
  rendered: RenderedUnit | undefined;
  components: ReadonlyMap<string, ComponentRow> | null;
  schedule: ReadonlyMap<number, ScheduledGame> | null;
}): UnitRatingBreakdown {
  const { role, team, rendered, components, schedule } = input;
  if (!rendered?.snapshotId) return unavailable(role, "missing");
  if (!components || !schedule) return unavailable(role, "lookup");
  const row = components.get(componentId(rendered.snapshotId, role));
  if (!row) return unavailable(role, "missing");

  if (row.v5SnapshotId !== rendered.snapshotId || row.ratingTeam !== rendered.ratingTeam || row.unitRole !== role
    || !rendered.sourceManifestSha256 || row.sourceManifestSha256 !== rendered.sourceManifestSha256
    || !within(row.ratingMean, rendered.rating, RATING_TOLERANCE)) return unavailable(role, "mismatch");

  const parsed = parseComponent(row);
  if (!parsed) return unavailable(role, "invalid");
  const exposure = parsed.evidence.reduce((sum, game) => sum + game.exposure, 0);
  const total = parsed.evidence.reduce((sum, game) => sum + game.contribution, parsed.priorContribution);
  if (!within(total, parsed.ratingMean, IDENTITY_TOLERANCE)
    || !within(exposure, parsed.usableExposure, IDENTITY_TOLERANCE)
    || parsed.completedGames !== parsed.evidence.length
    || (parsed.evidence.length > 0 && exposure <= 0)) return unavailable(role, "invalid");

  const byWeekThenId = (a: { week: number; gameId: number }, b: { week: number; gameId: number }) =>
    a.week - b.week || a.gameId - b.gameId;
  const opponent = (gameId: number) => opponentFor(schedule.get(gameId), team);
  const weighted = (pick: (game: ParsedComponent["evidence"][number]) => number) =>
    exposure > 0 ? parsed.evidence.reduce((sum, game) => sum + game.exposure * pick(game), 0) / exposure : null;

  return {
    status: "ready",
    role,
    rating: rendered.rating,
    rank: rendered.rank,
    priorWeight: parsed.priorWeight,
    priorContribution: parsed.priorContribution,
    rawPpp: weighted((game) => game.rawPpp),
    adjustedPpp: weighted((game) => game.adjustedPpp),
    possessions: exposure,
    completedGames: parsed.completedGames,
    games: [...parsed.evidence].sort(byWeekThenId).map((game) => ({ ...game, opponent: opponent(game.gameId) })),
    excluded: [...parsed.excluded].sort(byWeekThenId).map((game) => ({
      gameId: game.gameId,
      week: game.week,
      opponent: opponent(game.gameId),
      reason: excludedReasonLabel(game.reason),
    })),
  };
}
