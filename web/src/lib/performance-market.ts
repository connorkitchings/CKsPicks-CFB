/**
 * Model forecast versus the retained pre-kickoff betting line, for the same games.
 *
 * Pure (no database imports). The official record is settled at the shopped best quote and is
 * not touched here; only the error comparison uses the canonical line (`market_snapshots`).
 */

export type MarketTarget = "spread" | "total";
export type LineSource = "prekickoff" | "retrospective" | "unknown";

/** A model miss or line miss strictly larger than this many points is a "big miss". */
export const BIG_MISS_POINTS = 28;

/** The per-game facts the comparison reads; a structural subset of `GradedGamePick`. */
export interface MarketGame {
  gameId: number;
  week: number;
  homeTeam: string;
  awayTeam: string;
  homePoints: number | null;
  awayPoints: number | null;
  predictedSpread: number | null;
  predictedTotal: number | null;
  spreadResult: "win" | "loss" | "push" | null;
  totalResult: "win" | "loss" | "push" | null;
  canonicalSpread?: number | null;
  canonicalTotal?: number | null;
  spreadGradingVersion?: string | null;
  totalGradingVersion?: string | null;
}

export interface ComparedGame {
  gameId: number;
  week: number;
  homeTeam: string;
  awayTeam: string;
  /** Actual home margin (spread) or combined points (total). */
  actual: number;
  /** Model forecast and line-implied value on the same scale as `actual`. */
  model: number;
  line: number;
  /** Prediction minus actual. */
  modelError: number;
  lineError: number;
}

export interface MarketComparison {
  n: number;
  modelMiss: number;
  lineMiss: number;
  /** Mean signed error: positive leans toward the home team (spread) or high (total). */
  modelLean: number;
  lineLean: number;
  modelCloser: number;
  lineCloser: number;
  even: number;
  /** Games where one side was strictly closer; the percentage denominator (ties excluded). */
  decided: number;
  modelBigMisses: number;
  lineBigMisses: number;
}

export type LineSourceCounts = Record<LineSource, number>;

const PREKICKOFF_SUFFIX = ":retained_prekickoff";
const RETROSPECTIVE_SUFFIX = ":cfbd_retrospective";
const GRADING_PREFIX = "model_side_best_quote_v2";

/** Names the line behind a grade from `prediction_grades.grading_version`; anything else fails closed. */
export function lineSourceOf(gradingVersion: string | null | undefined): LineSource {
  if (typeof gradingVersion !== "string" || !gradingVersion.startsWith(GRADING_PREFIX)) return "unknown";
  if (gradingVersion === GRADING_PREFIX + PREKICKOFF_SUFFIX) return "prekickoff";
  if (gradingVersion === GRADING_PREFIX + RETROSPECTIVE_SUFFIX) return "retrospective";
  return "unknown";
}

interface Eligible {
  game: MarketGame;
  actual: number;
  model: number;
  line: number;
  source: LineSource;
}

/** Games with a grade for the target, final scores, a forecast and a canonical line. Any line source. */
function eligible(games: readonly MarketGame[], target: MarketTarget): Eligible[] {
  const out: Eligible[] = [];
  for (const game of games) {
    const result = target === "spread" ? game.spreadResult : game.totalResult;
    const forecast = target === "spread" ? game.predictedSpread : game.predictedTotal;
    const canonical = target === "spread" ? game.canonicalSpread : game.canonicalTotal;
    if (result == null || forecast == null || canonical == null) continue;
    if (game.homePoints == null || game.awayPoints == null) continue;
    const spread = target === "spread";
    out.push({
      game,
      actual: spread ? game.homePoints - game.awayPoints : game.homePoints + game.awayPoints,
      model: forecast,
      // Home-team spread of -7 implies a home margin of +7; a pick'em stays 0, never -0.
      line: spread ? (canonical === 0 ? 0 : -canonical) : canonical,
      source: lineSourceOf(target === "spread" ? game.spreadGradingVersion : game.totalGradingVersion),
    });
  }
  return out;
}

const compared = ({ game, actual, model, line }: Eligible): ComparedGame => ({
  gameId: game.gameId,
  week: game.week,
  homeTeam: game.homeTeam,
  awayTeam: game.awayTeam,
  actual,
  model,
  line,
  modelError: model - actual,
  lineError: line - actual,
});

/** The comparison set: eligible games whose line is the retained pre-kickoff line. Pushes included. */
export function comparableGames(games: readonly MarketGame[], target: MarketTarget): ComparedGame[] {
  return eligible(games, target).filter((row) => row.source === "prekickoff").map(compared);
}

/** Eligible games by line source; the non-pre-kickoff counts feed the exclusion footnote. */
export function lineSourceCounts(games: readonly MarketGame[], target: MarketTarget): LineSourceCounts {
  const counts: LineSourceCounts = { prekickoff: 0, retrospective: 0, unknown: 0 };
  for (const row of eligible(games, target)) counts[row.source] += 1;
  return counts;
}

const mean = (values: readonly number[]): number => values.reduce((sum, v) => sum + v, 0) / values.length;

function summarize(rows: readonly ComparedGame[], bigMiss: number): MarketComparison | null {
  if (rows.length === 0) return null;
  let modelCloser = 0;
  let lineCloser = 0;
  for (const row of rows) {
    const model = Math.abs(row.modelError);
    const line = Math.abs(row.lineError);
    if (model < line) modelCloser += 1;
    else if (line < model) lineCloser += 1;
  }
  return {
    n: rows.length,
    modelMiss: mean(rows.map((row) => Math.abs(row.modelError))),
    lineMiss: mean(rows.map((row) => Math.abs(row.lineError))),
    modelLean: mean(rows.map((row) => row.modelError)),
    lineLean: mean(rows.map((row) => row.lineError)),
    modelCloser,
    lineCloser,
    even: rows.length - modelCloser - lineCloser,
    decided: modelCloser + lineCloser,
    modelBigMisses: rows.filter((row) => Math.abs(row.modelError) > bigMiss).length,
    lineBigMisses: rows.filter((row) => Math.abs(row.lineError) > bigMiss).length,
  };
}

/** Average miss, lean, closer counts and big misses for the comparison set; null when it is empty. */
export function marketComparison(
  games: readonly MarketGame[],
  target: MarketTarget,
  bigMiss: number = BIG_MISS_POINTS,
): MarketComparison | null {
  return summarize(comparableGames(games, target), bigMiss);
}

